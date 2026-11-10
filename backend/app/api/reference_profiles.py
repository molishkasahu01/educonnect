from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.ai.analyzer import AIProfileAnalyzer
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.profile import ProfileIndicator, ReferenceProfile
from app.models.user import User
from app.schemas.reference import (
    ReferenceAnalysisResponse,
    ReferenceProfileCreate,
    ReferenceProfileOut,
)
from app.services.audit import record_audit_log

router = APIRouter(prefix="/reference-profiles", tags=["Reference Profiles"])


@router.post("", response_model=ReferenceProfileOut, status_code=status.HTTP_201_CREATED)
def create_reference_profile(
    payload: ReferenceProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    has_any = any([
        payload.linkedin_url,
        payload.full_name,
        payload.current_designation,
        payload.professional_bio,
        payload.career_history,
        payload.education_sector_experience,
        payload.skills,
        payload.additional_notes,
    ])
    if not has_any:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide reference profile fields (name, role, biography, career history, or reference URL).",
        )

    ref = ReferenceProfile(
        owner_id=current_user.id,
        linkedin_url=payload.linkedin_url.strip() if payload.linkedin_url else None,
        full_name=payload.full_name.strip() if payload.full_name else None,
        current_designation=payload.current_designation.strip() if payload.current_designation else None,
        current_organization=payload.current_organization.strip() if payload.current_organization else None,
        location=payload.location.strip() if payload.location else None,
        professional_bio=payload.professional_bio.strip() if payload.professional_bio else None,
        career_history=payload.career_history.strip() if payload.career_history else None,
        education_sector_experience=payload.education_sector_experience.strip() if payload.education_sector_experience else None,
        skills=[s.strip() for s in payload.skills if s.strip()],
        additional_notes=payload.additional_notes.strip() if payload.additional_notes else None,
        analysis_status="PENDING",
    )
    db.add(ref)
    db.flush()
    record_audit_log(
        db,
        action="REFERENCE_PROFILE_CREATED",
        resource_type="reference_profile",
        resource_id=str(ref.id),
        user_id=current_user.id,
    )
    db.commit()
    db.refresh(ref)
    return ReferenceProfileOut.model_validate(ref)


@router.get("", response_model=list[ReferenceProfileOut])
def list_reference_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ReferenceProfile)
        .filter(ReferenceProfile.owner_id == current_user.id, ReferenceProfile.deleted_at.is_(None))
        .order_by(ReferenceProfile.created_at.desc())
        .all()
    )
    return [ReferenceProfileOut.model_validate(r) for r in rows]


@router.get("/{profile_id}", response_model=ReferenceProfileOut)
def get_reference_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ref = (
        db.query(ReferenceProfile)
        .filter(
            ReferenceProfile.id == profile_id,
            ReferenceProfile.owner_id == current_user.id,
            ReferenceProfile.deleted_at.is_(None),
        )
        .first()
    )
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference profile not found")
    return ReferenceProfileOut.model_validate(ref)


@router.post("/{profile_id}/analyze", response_model=ReferenceAnalysisResponse)
def analyze_reference_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ref = (
        db.query(ReferenceProfile)
        .filter(
            ReferenceProfile.id == profile_id,
            ReferenceProfile.owner_id == current_user.id,
            ReferenceProfile.deleted_at.is_(None),
        )
        .first()
    )
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference profile not found")

    analyzer = AIProfileAnalyzer()
    analysis = analyzer.analyze_reference_profile(
        full_name=ref.full_name,
        linkedin_url=ref.linkedin_url,
        current_designation=ref.current_designation,
        current_organization=ref.current_organization,
        location=ref.location,
        professional_bio=ref.professional_bio,
        career_history=ref.career_history,
        education_sector_experience=ref.education_sector_experience,
        skills=ref.skills,
        additional_notes=ref.additional_notes,
    )

    ref.analysis_status = analysis["analysis_status"]
    ref.analysis_summary = analysis
    ref.normalized_document = analysis["normalized_document"]

    db.query(ProfileIndicator).filter(ProfileIndicator.reference_profile_id == ref.id).delete()
    for attr in analysis["attributes"]:
        db.add(
            ProfileIndicator(
                reference_profile_id=ref.id,
                category=attr["category"],
                attribute_name=attr["attribute_name"],
                attribute_value=attr["attribute_value"],
                evidence_text=attr["evidence_text"],
                source_reference=attr["source_reference"],
                classification_type=attr["classification_type"],
                confidence=attr["confidence"],
            )
        )

    record_audit_log(
        db,
        action="REFERENCE_PROFILE_ANALYZED",
        resource_type="reference_profile",
        resource_id=str(ref.id),
        user_id=current_user.id,
        details={"status": analysis["analysis_status"]},
    )
    db.commit()
    db.refresh(ref)

    attrs = analysis["attributes"]
    return ReferenceAnalysisResponse(
        reference_profile=ReferenceProfileOut.model_validate(ref),
        compliance_notice=analysis.get("compliance_notice"),
        missing_critical_fields=analysis.get("missing_critical_fields", []),
        observed_count=sum(1 for a in attrs if a["classification_type"] == "OBSERVED_FACT"),
        ai_derived_count=sum(1 for a in attrs if a["classification_type"] == "AI_DERIVED_CLASSIFICATION"),
        missing_count=sum(1 for a in attrs if a["classification_type"] == "MISSING_INFORMATION"),
    )


@router.delete("/{profile_id}")
def delete_reference_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ref = (
        db.query(ReferenceProfile)
        .filter(
            ReferenceProfile.id == profile_id,
            ReferenceProfile.owner_id == current_user.id,
            ReferenceProfile.deleted_at.is_(None),
        )
        .first()
    )
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference profile not found")
    ref.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Reference profile deleted"}
