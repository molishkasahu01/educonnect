from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.data_sources import (
    CSVAdapter,
    ManualProfileAdapter,
    OrganizationWebsiteAdapter,
    PublicDirectoryAdapter,
    is_restricted_social_url,
)
from app.models.profile import CandidateProfile
from app.models.user import User
from app.schemas.candidate import (
    CandidateImportResponse,
    CandidateProfileDetailOut,
    CandidateProfileSummaryOut,
    ManualCandidateImportRequest,
    PermittedUrlImportRequest,
)
from app.services.audit import record_audit_log
from app.services.ingestion import ingest_normalized_records

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("", response_model=dict)
def list_candidates(
    q: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    dataset_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CandidateProfile).filter(
        CandidateProfile.deleted_at.is_(None),
        CandidateProfile.is_duplicate_of.is_(None),
        CandidateProfile.verification_status.in_(["verified", "unverified"]),
        CandidateProfile.dataset_type.in_(["REAL_DATA", "USER_PROVIDED"]),
        CandidateProfile.visibility != "shared_benchmark",
        or_(
            CandidateProfile.owner_id == current_user.id,
            CandidateProfile.visibility == "shared_real",
        ),
    )

    if dataset_type:
        dt = dataset_type.strip().upper()
        if dt not in ("REAL_DATA", "USER_PROVIDED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dataset_type must be REAL_DATA or USER_PROVIDED.",
            )
        query = query.filter(CandidateProfile.dataset_type == dt)

    if verification_status:
        ver_norm = verification_status.strip().lower()
        if ver_norm not in ("verified", "unverified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="verification_status must be verified or unverified.",
            )
        query = query.filter(CandidateProfile.verification_status == ver_norm)
    if source:
        query = query.filter(CandidateProfile.primary_source.ilike(f"%{source}%"))
    if location:
        query = query.filter(CandidateProfile.location.ilike(f"%{location}%"))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                CandidateProfile.full_name.ilike(pattern),
                CandidateProfile.current_role.ilike(pattern),
                CandidateProfile.organization_name.ilike(pattern),
                CandidateProfile.professional_bio.ilike(pattern),
            )
        )

    total = query.count()
    items = (
        query.order_by(CandidateProfile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [CandidateProfileSummaryOut.model_validate(c) for c in items],
    }


@router.get("/{candidate_id}", response_model=CandidateProfileDetailOut)
def get_candidate_detail(
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cand = (
        db.query(CandidateProfile)
        .options(
            joinedload(CandidateProfile.experiences),
            joinedload(CandidateProfile.indicators),
            joinedload(CandidateProfile.sources),
        )
        .filter(
            CandidateProfile.id == candidate_id,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")
    return CandidateProfileDetailOut.model_validate(cand)


@router.post("/import", response_model=CandidateImportResponse)
async def import_candidates_csv(
    file: UploadFile = File(...),
    source_name: str = Form("user_authorized_csv"),
    verification_status: str = Form("unverified"),
    dataset_type: str = Form("USER_PROVIDED"),
    authorization_confirmed: bool = Form(...),
    authorization_note: str = Form("User confirmed authorized data upload"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not authorization_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload authorization confirmation is required before ingesting candidate profiles.",
        )

    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only UTF-8 .csv files are supported for bulk upload.",
        )

    if verification_status not in ("verified", "unverified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="verification_status must be verified or unverified; synthetic data is disabled.",
        )

    norm_dataset_type = dataset_type.strip().upper()
    if norm_dataset_type not in ("USER_PROVIDED", "REAL_DATA"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dataset_type must be USER_PROVIDED or REAL_DATA.",
        )

    settings = get_settings()
    raw_bytes = await file.read()
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
        )
    if not raw_bytes.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV file is empty.")

    adapter = CSVAdapter()
    records = adapter.ingest(
        raw_bytes,
        source_name=source_name.strip(),
        default_verification_status=verification_status,
        usage_restrictions=authorization_note.strip(),
        dataset_type=norm_dataset_type,
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid candidate rows with names found in CSV.",
        )

    result = ingest_normalized_records(
        db=db,
        records=records,
        owner_id=current_user.id,
        visibility="private",
        dataset_type=norm_dataset_type,
        adapter_type="csv",
        authorization_note=authorization_note.strip(),
        uploaded_by_user_id=current_user.id,
        compute_embeddings=True,
    )
    record_audit_log(
        db,
        action="CANDIDATES_CSV_IMPORTED",
        resource_type="candidate_import",
        resource_id=source_name,
        user_id=current_user.id,
        details={
            "filename": file.filename,
            "imported": result["imported_count"],
            "merged": result["merged_duplicates_count"],
            "dataset_type": norm_dataset_type,
            "authorization_note": authorization_note,
        },
    )
    db.commit()

    return CandidateImportResponse(
        imported_count=result["imported_count"],
        merged_duplicates_count=result["merged_duplicates_count"],
        skipped_count=result["skipped_count"],
        source_name=source_name,
        verification_status=verification_status,
        dataset_type=norm_dataset_type,
        authorization_recorded=True,
        warnings=result["warnings"],
        candidate_ids=result["candidate_ids"],
    )


@router.post("/manual", response_model=CandidateImportResponse)
def import_manual_candidate(
    payload: ManualCandidateImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.authorization_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization confirmation is required.",
        )
    adapter = ManualProfileAdapter()
    records = adapter.ingest(payload)
    effective_dt = payload.dataset_type
    result = ingest_normalized_records(
        db=db,
        records=records,
        owner_id=current_user.id,
        visibility="private",
        dataset_type=effective_dt,
        adapter_type="manual",
        authorization_note=payload.authorization_note,
        uploaded_by_user_id=current_user.id,
        compute_embeddings=True,
    )
    record_audit_log(
        db,
        action="CANDIDATE_MANUAL_ADDED",
        resource_type="candidate_import",
        user_id=current_user.id,
        details={"source_name": payload.source_name, "dataset_type": effective_dt, "imported": result["imported_count"]},
    )
    db.commit()
    return CandidateImportResponse(
        imported_count=result["imported_count"],
        merged_duplicates_count=result["merged_duplicates_count"],
        skipped_count=result["skipped_count"],
        source_name=payload.source_name,
        verification_status=payload.verification_status,
        dataset_type=effective_dt,
        authorization_recorded=True,
        warnings=result["warnings"],
        candidate_ids=result["candidate_ids"],
    )


@router.post("/fetch-url", response_model=CandidateImportResponse)
def fetch_permitted_web_sources(
    payload: PermittedUrlImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Collect real candidate profiles from permitted official school websites or education directories."""
    if not payload.authorization_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization confirmation is required before collecting external public records.",
        )

    all_records = []
    warnings: list[str] = []
    adapter = (
        OrganizationWebsiteAdapter()
        if payload.source_type == "organization_website"
        else PublicDirectoryAdapter()
    )

    for raw_url in payload.urls:
        url = raw_url.strip()
        if not url:
            continue
        if is_restricted_social_url(url):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Blocked domain by compliance policy: {url}. Automated LinkedIn scraping is prohibited.",
            )
        try:
            recs = adapter.fetch_url(url, source_name=payload.source_name.strip())
            if not recs:
                warnings.append(f"No structured profile entries extracted from {url}")
            all_records.extend(recs)
        except PermissionError as exc:
            warnings.append(f"Access denied / robots blocked for {url}: {exc}")
        except Exception as exc:
            warnings.append(f"Fetch failed for {url}: {exc}")

    if not all_records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No extractable professional profiles were retrieved from the provided URL(s). "
                + ("; ".join(warnings) if warnings else "Verify the URL exposes JSON, JSON-LD Person, or structured leadership cards.")
            ),
        )

    result = ingest_normalized_records(
        db=db,
        records=all_records,
        owner_id=current_user.id,
        visibility="private",
        dataset_type="REAL_DATA",
        adapter_type=payload.source_type,
        authorization_note=payload.authorization_note.strip(),
        uploaded_by_user_id=current_user.id,
        compute_embeddings=True,
    )
    record_audit_log(
        db,
        action="CANDIDATES_WEB_SOURCE_FETCHED",
        resource_type="candidate_import",
        resource_id=payload.source_name,
        user_id=current_user.id,
        details={"urls": payload.urls, "imported": result["imported_count"]},
    )
    db.commit()

    return CandidateImportResponse(
        imported_count=result["imported_count"],
        merged_duplicates_count=result["merged_duplicates_count"],
        skipped_count=result["skipped_count"],
        source_name=payload.source_name,
        verification_status="verified" if any(r.verification_status == "verified" for r in all_records) else "unverified",
        dataset_type="REAL_DATA",
        authorization_recorded=True,
        warnings=warnings + result["warnings"],
        candidate_ids=result["candidate_ids"],
    )
