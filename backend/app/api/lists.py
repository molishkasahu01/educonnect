from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.list_eval import SavedList, SavedListProfile
from app.models.profile import CandidateProfile
from app.models.user import User
from app.schemas.candidate import CandidateProfileSummaryOut
from app.schemas.list_admin import (
    SavedListAddCandidate,
    SavedListCreate,
    SavedListItemOut,
    SavedListOut,
)
from app.services.audit import record_audit_log

router = APIRouter(prefix="/lists", tags=["Saved Lists"])


def _serialize_list(db: Session, lst: SavedList) -> SavedListOut:
    items_out: list[SavedListItemOut] = []
    cand_ids = [p.candidate_id for p in lst.profiles]
    cands = (
        {c.id: c for c in db.query(CandidateProfile).filter(CandidateProfile.id.in_(cand_ids), CandidateProfile.deleted_at.is_(None)).all()}
        if cand_ids
        else {}
    )
    for item in lst.profiles:
        cand = cands.get(item.candidate_id)
        if not cand:
            continue
        items_out.append(
            SavedListItemOut(
                id=item.id,
                candidate_id=item.candidate_id,
                discovery_job_id=item.discovery_job_id,
                notes=item.notes,
                added_at=item.added_at,
                candidate=CandidateProfileSummaryOut.model_validate(cand),
            )
        )
    return SavedListOut(
        id=lst.id,
        owner_id=lst.owner_id,
        name=lst.name,
        description=lst.description,
        created_at=lst.created_at,
        updated_at=lst.updated_at,
        candidate_count=len(items_out),
        items=items_out,
    )


@router.post("", response_model=SavedListOut, status_code=status.HTTP_201_CREATED)
def create_saved_list(
    payload: SavedListCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lst = SavedList(
        owner_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
    )
    db.add(lst)
    db.flush()
    record_audit_log(
        db,
        action="SAVED_LIST_CREATED",
        resource_type="saved_list",
        resource_id=str(lst.id),
        user_id=current_user.id,
    )
    db.commit()
    db.refresh(lst)
    return _serialize_list(db, lst)


@router.get("", response_model=list[SavedListOut])
def get_saved_lists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SavedList)
        .options(joinedload(SavedList.profiles))
        .filter(SavedList.owner_id == current_user.id, SavedList.deleted_at.is_(None))
        .order_by(SavedList.updated_at.desc())
        .all()
    )
    return [_serialize_list(db, lst) for lst in rows]


@router.get("/{list_id}", response_model=SavedListOut)
def get_saved_list_detail(
    list_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lst = (
        db.query(SavedList)
        .options(joinedload(SavedList.profiles))
        .filter(
            SavedList.id == list_id,
            SavedList.owner_id == current_user.id,
            SavedList.deleted_at.is_(None),
        )
        .first()
    )
    if not lst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved list not found")
    return _serialize_list(db, lst)


@router.post("/{list_id}/candidates", response_model=SavedListOut)
def add_candidate_to_list(
    list_id: UUID,
    payload: SavedListAddCandidate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lst = (
        db.query(SavedList)
        .filter(
            SavedList.id == list_id,
            SavedList.owner_id == current_user.id,
            SavedList.deleted_at.is_(None),
        )
        .first()
    )
    if not lst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved list not found")

    cand = (
        db.query(CandidateProfile)
        .filter(
            CandidateProfile.id == payload.candidate_id,
            CandidateProfile.deleted_at.is_(None),
            CandidateProfile.verification_status.in_(["verified", "unverified"]),
            CandidateProfile.visibility != "shared_benchmark",
            or_(
                CandidateProfile.visibility == "shared_real",
                CandidateProfile.owner_id == current_user.id,
            ),
        )
        .first()
    )
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found or inaccessible")

    existing = (
        db.query(SavedListProfile)
        .filter(
            SavedListProfile.saved_list_id == lst.id,
            SavedListProfile.candidate_id == cand.id,
        )
        .first()
    )
    if not existing:
        db.add(
            SavedListProfile(
                saved_list_id=lst.id,
                candidate_id=cand.id,
                discovery_job_id=payload.discovery_job_id,
                notes=payload.notes,
            )
        )
        lst.updated_at = datetime.now(timezone.utc)
        db.commit()

    db.refresh(lst)
    return _serialize_list(db, lst)


@router.delete("/{list_id}/candidates/{candidate_id}", response_model=SavedListOut)
def remove_candidate_from_list(
    list_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lst = (
        db.query(SavedList)
        .filter(
            SavedList.id == list_id,
            SavedList.owner_id == current_user.id,
            SavedList.deleted_at.is_(None),
        )
        .first()
    )
    if not lst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved list not found")

    item = (
        db.query(SavedListProfile)
        .filter(
            SavedListProfile.saved_list_id == lst.id,
            SavedListProfile.candidate_id == candidate_id,
        )
        .first()
    )
    if item:
        db.delete(item)
        lst.updated_at = datetime.now(timezone.utc)
        db.commit()

    db.refresh(lst)
    return _serialize_list(db, lst)


@router.delete("/{list_id}")
def delete_saved_list(
    list_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lst = (
        db.query(SavedList)
        .filter(
            SavedList.id == list_id,
            SavedList.owner_id == current_user.id,
            SavedList.deleted_at.is_(None),
        )
        .first()
    )
    if not lst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved list not found")
    lst.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Saved list deleted"}
