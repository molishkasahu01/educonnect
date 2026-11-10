from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.discovery.pipeline import get_active_ranking_config
from app.models.discovery import DiscoveryJob, DiscoveryResult
from app.models.profile import CandidateProfile, ReferenceProfile
from app.models.user import User
from app.schemas.candidate import CandidateProfileSummaryOut
from app.schemas.discovery import (
    DiscoveryCreateRequest,
    DiscoveryJobOut,
    DiscoveryResultItemOut,
    DiscoveryResultsPageOut,
    RankingExplanationOut,
    RankingScoreOut,
)
from app.services.audit import record_audit_log
from app.services.real_discovery import get_provider_statuses
from app.workers.tasks import enqueue_discovery_job

router = APIRouter(prefix="/discovery", tags=["Discovery"])


@router.get("/providers")
def list_discovery_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return connection status, authorization policy, and record counts per data environment."""
    return get_provider_statuses(db, current_user.id)


@router.post("", response_model=DiscoveryJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_discovery_job(
    payload: DiscoveryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ref = (
        db.query(ReferenceProfile)
        .filter(
            ReferenceProfile.id == payload.reference_profile_id,
            ReferenceProfile.owner_id == current_user.id,
            ReferenceProfile.deleted_at.is_(None),
        )
        .first()
    )
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference profile not found")

    if ref.analysis_status == "NEEDS_MORE_INFO" and not (ref.normalized_document or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reference profile lacks sufficient information. Please add role, biography, or career history before starting discovery.",
        )

    # Idempotency check
    if payload.idempotency_key:
        existing_job = (
            db.query(DiscoveryJob)
            .filter(
                DiscoveryJob.owner_id == current_user.id,
                DiscoveryJob.idempotency_key == payload.idempotency_key,
            )
            .first()
        )
        if existing_job:
            return DiscoveryJobOut.model_validate(existing_job)

    weights, rank_version = get_active_ranking_config(db)
    settings = get_settings()

    job = DiscoveryJob(
        owner_id=current_user.id,
        reference_profile_id=ref.id,
        idempotency_key=payload.idempotency_key,
        status="PENDING",
        current_stage="QUEUED",
        progress_percent=0,
        stage_logs=[{
            "stage": "QUEUED",
            "progress_percent": 0,
            "detail": f"Discovery job accepted in {payload.discovery_mode} mode and queued",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
        ranking_model_version=rank_version,
        embedding_model_name=settings.embedding_model_name,
        discovery_mode=payload.discovery_mode,
        selected_sources=payload.selected_sources,
        weights_snapshot=weights,
        filters_applied=payload.filters,
    )
    db.add(job)
    db.flush()
    record_audit_log(
        db,
        action="DISCOVERY_JOB_CREATED",
        resource_type="discovery_job",
        resource_id=str(job.id),
        user_id=current_user.id,
    )
    db.commit()

    task_id = enqueue_discovery_job(job.id)
    job.celery_task_id = task_id
    db.commit()
    db.refresh(job)
    return DiscoveryJobOut.model_validate(job)


@router.get("", response_model=list[DiscoveryJobOut])
def list_discovery_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(DiscoveryJob)
        .filter(DiscoveryJob.owner_id == current_user.id)
        .order_by(DiscoveryJob.created_at.desc())
        .all()
    )
    return [DiscoveryJobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=DiscoveryJobOut)
def get_discovery_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(DiscoveryJob)
        .filter(DiscoveryJob.id == job_id, DiscoveryJob.owner_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery job not found")
    return DiscoveryJobOut.model_validate(job)


@router.post("/{job_id}/retry", response_model=DiscoveryJobOut)
def retry_discovery_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(DiscoveryJob)
        .filter(DiscoveryJob.id == job_id, DiscoveryJob.owner_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery job not found")
    if job.status not in ("FAILED", "COMPLETED"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot retry job in status {job.status}")

    job.status = "RETRYING"
    job.current_stage = "QUEUED"
    job.progress_percent = 0
    job.error_message = None
    job.retry_count += 1
    db.commit()

    task_id = enqueue_discovery_job(job.id)
    job.celery_task_id = task_id
    db.commit()
    db.refresh(job)
    return DiscoveryJobOut.model_validate(job)


@router.get("/{job_id}/results", response_model=DiscoveryResultsPageOut)
def get_discovery_results(
    job_id: UUID,
    q: Optional[str] = Query(None, description="Search candidate name, role, org, or bio"),
    role: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    min_experience: Optional[float] = Query(None, ge=0),
    indicator: Optional[str] = Query(None, description="Filter by school ecosystem indicator"),
    verification_status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    relevance_tier: Optional[str] = Query(None),
    sort_by: str = Query("relevance", pattern="^(relevance|confidence|school_indicators|role_similarity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(DiscoveryJob)
        .filter(DiscoveryJob.id == job_id, DiscoveryJob.owner_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery job not found")

    ref = db.query(ReferenceProfile).filter(ReferenceProfile.id == job.reference_profile_id).first()

    raw_results = (
        db.query(DiscoveryResult)
        .options(
            joinedload(DiscoveryResult.ranking_score),
            joinedload(DiscoveryResult.explanation),
        )
        .filter(DiscoveryResult.discovery_job_id == job.id)
        .all()
    )

    cand_ids = [r.candidate_id for r in raw_results]
    candidates_map = {
        c.id: c
        for c in db.query(CandidateProfile).filter(CandidateProfile.id.in_(cand_ids)).all()
    } if cand_ids else {}

    provenance_summary: dict[str, int] = {"verified": 0, "unverified": 0}
    filtered_items: list[tuple[DiscoveryResult, CandidateProfile]] = []

    q_low = q.lower().strip() if q else ""
    role_low = role.lower().strip() if role else ""
    loc_low = location.lower().strip() if location else ""
    ind_low = indicator.lower().strip() if indicator else ""
    ver_low = verification_status.lower().strip() if verification_status else ""
    src_low = source.lower().strip() if source else ""
    tier_up = relevance_tier.upper().strip() if relevance_tier else ""

    for res in raw_results:
        cand = candidates_map.get(res.candidate_id)
        if not cand or cand.deleted_at is not None:
            continue
        provenance_summary[cand.verification_status] = provenance_summary.get(cand.verification_status, 0) + 1

        if q_low:
            haystack = f"{cand.full_name} {cand.current_role or ''} {cand.organization_name or ''} {cand.professional_bio or ''} {' '.join(cand.school_indicators or [])}".lower()
            if q_low not in haystack:
                continue
        if role_low and role_low not in (cand.current_role or "").lower():
            continue
        if loc_low and loc_low not in (cand.location or "").lower():
            continue
        if min_experience is not None and (cand.experience_years is None or cand.experience_years < min_experience):
            continue
        if ind_low:
            all_inds = " ".join(cand.school_indicators or []).lower() + " " + (cand.current_role or "").lower() + " " + (cand.professional_bio or "").lower()
            if ind_low not in all_inds:
                continue
        if ver_low and cand.verification_status.lower() != ver_low:
            continue
        if src_low and src_low not in cand.primary_source.lower():
            continue
        if tier_up and res.relevance_tier != tier_up:
            continue

        filtered_items.append((res, cand))

    # Sorting
    if sort_by == "confidence":
        filtered_items.sort(key=lambda x: (x[0].evidence_confidence, x[0].relevance_score), reverse=True)
    elif sort_by == "school_indicators":
        filtered_items.sort(
            key=lambda x: (len(x[1].school_indicators or []), x[0].ranking_score.school_ecosystem_relevance if x[0].ranking_score else 0.0),
            reverse=True,
        )
    elif sort_by == "role_similarity":
        filtered_items.sort(
            key=lambda x: (x[0].ranking_score.professional_role_similarity if x[0].ranking_score else 0.0, x[0].relevance_score),
            reverse=True,
        )
    else:
        filtered_items.sort(key=lambda x: (x[0].relevance_score, x[0].evidence_confidence), reverse=True)

    total_matched = len(filtered_items)
    start = (page - 1) * page_size
    page_slice = filtered_items[start : start + page_size]

    items_out: list[DiscoveryResultItemOut] = []
    for res, cand in page_slice:
        if not res.ranking_score or not res.explanation:
            continue
        items_out.append(
            DiscoveryResultItemOut(
                id=res.id,
                rank_position=res.rank_position,
                relevance_score=res.relevance_score,
                evidence_confidence=res.evidence_confidence,
                meets_minimum_evidence=res.meets_minimum_evidence,
                relevance_tier=res.relevance_tier,
                candidate=CandidateProfileSummaryOut.model_validate(cand),
                ranking_score=RankingScoreOut.model_validate(res.ranking_score),
                explanation=RankingExplanationOut.model_validate(res.explanation),
            )
        )

    empty_state_message = None
    if job.total_candidates_evaluated == 0:
        empty_state_message = (
            "No verified or authorized professional profiles were found for this discovery. "
            "Connect an authorized source or import genuine professional records."
        )

    return DiscoveryResultsPageOut(
        job=DiscoveryJobOut.model_validate(job),
        reference_profile_summary={
            "id": str(ref.id) if ref else "",
            "full_name": ref.full_name if ref else "",
            "current_designation": ref.current_designation if ref else "",
            "current_organization": ref.current_organization if ref else "",
            "location": ref.location if ref else "",
            "school_indicators": (ref.analysis_summary or {}).get("school_indicators", []) if ref else [],
        },
        dataset_provenance_summary=provenance_summary,
        discovery_mode=job.discovery_mode,
        selected_sources=job.selected_sources or [],
        provider_diagnostics=job.provider_diagnostics or {},
        empty_state_message=empty_state_message,
        total_matched=total_matched,
        page=page,
        page_size=page_size,
        items=items_out,
    )
