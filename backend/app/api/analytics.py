from collections import Counter
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.discovery import DiscoveryJob, DiscoveryResult
from app.models.profile import CandidateProfile
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
def get_dashboard_analytics(
    dataset_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real database-backed analytics across verified and user-authorized real records only."""
    all_visible_cands = (
        db.query(CandidateProfile)
        .filter(
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
        .all()
    )
    all_jobs = (
        db.query(DiscoveryJob)
        .filter(
            DiscoveryJob.owner_id == current_user.id,
            DiscoveryJob.discovery_mode.in_(["REAL_DATA", "USER_PROVIDED", "ALL_AUTHORIZED"]),
        )
        .order_by(DiscoveryJob.created_at.asc())
        .all()
    )

    real_data_count = sum(1 for c in all_visible_cands if c.dataset_type == "REAL_DATA")
    user_provided_count = sum(1 for c in all_visible_cands if c.dataset_type == "USER_PROVIDED")

    dt_filter = dataset_type.strip().upper() if dataset_type else None
    if dt_filter:
        if dt_filter not in ("REAL_DATA", "USER_PROVIDED", "ALL_AUTHORIZED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dataset_type must be REAL_DATA, USER_PROVIDED, or ALL_AUTHORIZED.",
            )
        if dt_filter == "ALL_AUTHORIZED":
            cands = all_visible_cands
            jobs = all_jobs
        else:
            cands = [c for c in all_visible_cands if c.dataset_type == dt_filter]
            jobs = [j for j in all_jobs if j.discovery_mode == dt_filter]
    else:
        cands = all_visible_cands
        jobs = all_jobs

    job_ids = [j.id for j in jobs]
    results = (
        db.query(DiscoveryResult)
        .filter(DiscoveryResult.discovery_job_id.in_(job_ids))
        .all()
        if job_ids
        else []
    )

    verified_count = sum(1 for c in cands if c.verification_status == "verified")
    unverified_count = sum(1 for c in cands if c.verification_status == "unverified")

    relevant_discovered = sum(1 for r in results if r.relevance_tier == "HIGHLY_RELEVANT")
    avg_relevance = round(sum(r.relevance_score for r in results) / len(results), 2) if results else 0.0
    avg_confidence = round(sum(r.evidence_confidence for r in results) / len(results), 2) if results else 0.0

    # Professional segment distribution
    seg_counter: Counter[str] = Counter()
    loc_counter: Counter[str] = Counter()
    src_counter: Counter[str] = Counter()
    for c in cands:
        segs = c.education_segments or ["General / Non-K12"]
        seg_counter[segs[0]] += 1
        loc_counter[c.location or "Unspecified"] += 1
        src_counter[c.primary_source] += 1

    # Relevance score histogram buckets
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for r in results:
        s = r.relevance_score
        if s < 20:
            buckets["0-20"] += 1
        elif s < 40:
            buckets["20-40"] += 1
        elif s < 60:
            buckets["40-60"] += 1
        elif s < 80:
            buckets["60-80"] += 1
        else:
            buckets["80-100"] += 1

    discovery_history = [
        {
            "job_id": str(j.id)[:8],
            "created_at": j.created_at.strftime("%Y-%m-%d %H:%M"),
            "status": j.status,
            "evaluated": j.total_candidates_evaluated,
            "relevant": j.relevant_candidates_count,
            "processing_time_ms": j.processing_time_ms or 0,
        }
        for j in jobs[-15:]
    ]

    return {
        "active_dataset_filter": dt_filter or "ALL_AUTHORIZED",
        "metrics": {
            "total_discovery_jobs": len(jobs),
            "total_candidate_profiles": len(cands),
            "real_data_profiles": real_data_count,
            "user_provided_profiles": user_provided_count,
            "relevant_professionals_discovered": relevant_discovered,
            "verified_profiles": verified_count,
            "unverified_profiles": unverified_count,
            "average_relevance_score": avg_relevance,
            "average_evidence_confidence": avg_confidence,
        },
        "environment_breakdown": [
            {"environment": "REAL_DATA", "label": "Real External Sources", "count": real_data_count},
            {"environment": "USER_PROVIDED", "label": "Authorized Uploads", "count": user_provided_count},
        ],
        "charts": {
            "segment_distribution": [
                {"name": k, "count": v} for k, v in seg_counter.most_common(10)
            ],
            "relevance_distribution": [
                {"range": k, "count": v} for k, v in buckets.items()
            ],
            "location_distribution": [
                {"location": k, "count": v} for k, v in loc_counter.most_common(10)
            ],
            "discovery_history": discovery_history,
            "source_distribution": [
                {"source": k, "count": v} for k, v in src_counter.most_common(8)
            ],
            "verification_distribution": [
                {"status": "verified", "count": verified_count},
                {"status": "unverified", "count": unverified_count},
            ],
        },
    }
