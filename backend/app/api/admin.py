from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.ai.embeddings import embedding_service
from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.data_sources.base import build_normalized_professional_document
from app.discovery.pipeline import get_active_ranking_config
from app.models.discovery import ModelVersion, ProfileEmbedding
from app.models.list_eval import AuditLog, BenchmarkLabel, EvaluationRun
from app.models.organization import DataSource
from app.models.profile import CandidateProfile, ReferenceProfile
from app.models.user import User
from app.ranking.engine import HybridRankingEngine
from app.ranking.evaluation import compute_keyword_baseline_scores, evaluate_ranking_order
from app.schemas.list_admin import (
    AuditLogOut,
    DataSourceOut,
    DataSourceToggleRequest,
    ModelConfigUpdate,
    RankingWeightsConfig,
)
from app.services.audit import record_audit_log

router = APIRouter(prefix="/admin", tags=["Admin"])


def execute_benchmark_evaluation(
    db: Session,
    user_id: Optional[UUID] = None,
    reference_profile_id: Optional[UUID] = None,
) -> EvaluationRun:
    labels = db.query(BenchmarkLabel).all()
    if not labels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genuine labeled evaluation dataset found. Import real candidate profiles and genuine evaluation labels before running evaluation.",
        )

    label_map = {lbl.candidate_source_record_id: lbl.label for lbl in labels}
    cands = (
        db.query(CandidateProfile)
        .filter(
            CandidateProfile.deleted_at.is_(None),
            CandidateProfile.verification_status.in_(["verified", "unverified"]),
            CandidateProfile.dataset_type.in_(["REAL_DATA", "USER_PROVIDED"]),
            CandidateProfile.source_record_id.in_(list(label_map.keys())),
        )
        .all()
    )
    if not cands:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genuine non-synthetic candidates matched existing evaluation labels.",
        )

    ref_obj: Optional[ReferenceProfile] = None
    if reference_profile_id:
        ref_obj = (
            db.query(ReferenceProfile)
            .filter(ReferenceProfile.id == reference_profile_id, ReferenceProfile.deleted_at.is_(None))
            .first()
        )
    if not ref_obj:
        ref_obj = (
            db.query(ReferenceProfile)
            .filter(ReferenceProfile.deleted_at.is_(None))
            .order_by(ReferenceProfile.created_at.desc())
            .first()
        )
    if not ref_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create or select a genuine reference profile before running IR evaluation.",
        )

    summary = ref_obj.analysis_summary or {}
    eval_ref_dict = {
        "full_name": ref_obj.full_name or "Reference Profile",
        "current_designation": ref_obj.current_designation,
        "current_organization": ref_obj.current_organization,
        "location": ref_obj.location,
        "professional_bio": f"{ref_obj.professional_bio or ''} {ref_obj.career_history or ''}".strip(),
        "experience_years": summary.get("experience_years"),
        "school_indicators": summary.get("school_indicators") or [],
        "organizations": summary.get("organizations") or [],
        "influence_indicators": summary.get("influence_indicators") or [],
        "skills": ref_obj.skills or [],
    }
    ref_doc = ref_obj.normalized_document or build_normalized_professional_document(
        full_name=eval_ref_dict["full_name"],
        current_role=eval_ref_dict["current_designation"],
        organization=eval_ref_dict["current_organization"],
        location=eval_ref_dict["location"],
        professional_bio=eval_ref_dict["professional_bio"],
        school_indicators=eval_ref_dict["school_indicators"],
        organizations=eval_ref_dict["organizations"],
        skills=eval_ref_dict["skills"],
        influence_indicators=eval_ref_dict["influence_indicators"],
    )

    cand_dicts = [
        {
            "id": c.id,
            "source_record_id": c.source_record_id,
            "full_name": c.full_name,
            "current_role": c.current_role,
            "organization_name": c.organization_name,
            "location": c.location,
            "professional_bio": c.professional_bio,
            "experience_years": c.experience_years,
            "education_segments": c.education_segments,
            "school_indicators": c.school_indicators,
            "organizations_list": c.organizations_list,
            "skills": c.skills,
            "influence_indicators": c.influence_indicators,
            "primary_source": c.primary_source,
            "source_url": c.source_url,
            "verification_status": c.verification_status,
            "data_confidence": c.data_confidence,
        }
        for c in cands
    ]

    # 1. Keyword-only baseline
    kw_ranked = compute_keyword_baseline_scores(ref_doc, cand_dicts)
    kw_ids = [rid for rid, _ in kw_ranked]
    kw_metrics = evaluate_ranking_order(kw_ids, label_map)

    # 2. Semantic similarity baseline
    model_name = embedding_service.get_active_model_name()
    ref_vec = embedding_service.encode_text(ref_doc, model_name=model_name)
    cand_ids = [c.id for c in cands]
    emb_rows = (
        db.query(ProfileEmbedding)
        .filter(ProfileEmbedding.candidate_id.in_(cand_ids), ProfileEmbedding.model_name == model_name)
        .all()
    )
    emb_map = {r.candidate_id: r.embedding for r in emb_rows if r.candidate_id}

    sem_scored: list[tuple[str, float, dict]] = []
    for cd in cand_dicts:
        vec = emb_map.get(cd["id"])
        if not vec:
            doc = build_normalized_professional_document(
                full_name=cd["full_name"],
                current_role=cd["current_role"],
                organization=cd["organization_name"],
                location=cd["location"],
                professional_bio=cd["professional_bio"],
                education_segments=cd["education_segments"],
                school_indicators=cd["school_indicators"],
                organizations=cd["organizations_list"],
                skills=cd["skills"],
                influence_indicators=cd["influence_indicators"],
            )
            vec = embedding_service.encode_text(doc, model_name=model_name)
        cos_sim = embedding_service.cosine_similarity(ref_vec, vec)
        sem_100 = embedding_service.normalize_cosine_to_100(cos_sim)
        sem_scored.append((cd["source_record_id"], sem_100, cd))

    sem_scored.sort(key=lambda x: x[1], reverse=True)
    sem_ids = [rid for rid, _, _ in sem_scored]
    sem_metrics = evaluate_ranking_order(sem_ids, label_map)

    # 3. Hybrid ranking model
    weights, rank_ver = get_active_ranking_config(db)
    engine = HybridRankingEngine(weights=weights, model_version=rank_ver)
    hyb_scored: list[tuple[str, float]] = []
    for rid, sem_100, cd in sem_scored:
        comp = engine.score_candidate(eval_ref_dict, cd, sem_100)
        hyb_scored.append((rid, comp.relevance_score))
    hyb_scored.sort(key=lambda x: x[1], reverse=True)
    hyb_ids = [rid for rid, _ in hyb_scored]
    hyb_metrics = evaluate_ranking_order(hyb_ids, label_map)

    run = EvaluationRun(
        benchmark_name=labels[0].benchmark_name,
        model_comparison={
            "keyword_baseline": kw_metrics,
            "semantic_baseline": sem_metrics,
            "hybrid_ranking": hyb_metrics,
            "embedding_model": model_name,
            "ranking_model_version": rank_ver,
        },
        relevance_treatment_note=(
            "Precision@10, Precision@20, Recall@20, and MRR treat RELEVANT as positive (1) and "
            "PARTIALLY_RELEVANT/IRRELEVANT as negative (0). NDCG@10 uses graded relevance "
            "(RELEVANT=2, PARTIALLY_RELEVANT=1, IRRELEVANT=0)."
        ),
        dataset_disclaimer=(
            f"Evaluated strictly on {len(cands)} genuine labeled non-synthetic candidate records "
            f"against reference profile '{eval_ref_dict['full_name']}'."
        ),
        total_candidates=len(cands),
        run_by_user_id=user_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/models")
def get_models(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    versions = db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
    return {
        "active_config": {
            "embedding_model_name": settings.embedding_model_name,
            "embedding_dimension": settings.embedding_dimension,
            "cross_encoder_enabled": settings.cross_encoder_enabled,
            "cross_encoder_model_name": settings.cross_encoder_model_name,
            "llm_provider": settings.llm_provider,
        },
        "registered_versions": [
            {
                "id": str(v.id),
                "name": v.name,
                "model_type": v.model_type,
                "version": v.version,
                "dimension": v.dimension,
                "config": v.config,
                "is_active": v.is_active,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
    }


@router.put("/models")
def update_model_config(
    payload: ModelConfigUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if payload.embedding_model_name is not None:
        settings.embedding_model_name = payload.embedding_model_name
    if payload.cross_encoder_enabled is not None:
        settings.cross_encoder_enabled = payload.cross_encoder_enabled
    if payload.cross_encoder_model_name is not None:
        settings.cross_encoder_model_name = payload.cross_encoder_model_name

    record_audit_log(
        db,
        action="ADMIN_MODEL_CONFIG_UPDATED",
        resource_type="model_config",
        user_id=admin.id,
        details=payload.model_dump(exclude_none=True),
    )
    db.commit()
    return {
        "message": "Model configuration updated",
        "active_config": {
            "embedding_model_name": settings.embedding_model_name,
            "cross_encoder_enabled": settings.cross_encoder_enabled,
            "cross_encoder_model_name": settings.cross_encoder_model_name,
        },
    }


@router.get("/ranking-weights")
def get_ranking_weights(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    weights, version = get_active_ranking_config(db)
    return {"version": version, "weights": weights}


@router.put("/ranking-weights")
def update_ranking_weights(
    payload: RankingWeightsConfig,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.query(ModelVersion).filter(ModelVersion.model_type == "ranking").update({"is_active": False})
    count = db.query(ModelVersion).filter(ModelVersion.model_type == "ranking").count()
    new_ver = f"hybrid-v1.{count + 1}"
    weights_dict = payload.model_dump()
    mv = ModelVersion(
        name="edxso_hybrid_ranker",
        model_type="ranking",
        version=new_ver,
        config=weights_dict,
        is_active=True,
    )
    db.add(mv)
    record_audit_log(
        db,
        action="ADMIN_RANKING_WEIGHTS_UPDATED",
        resource_type="ranking_weights",
        resource_id=new_ver,
        user_id=admin.id,
        details=weights_dict,
    )
    db.commit()
    return {"version": new_ver, "weights": weights_dict}


@router.get("/data-sources", response_model=list[DataSourceOut])
def list_data_sources(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sources = db.query(DataSource).order_by(DataSource.created_at.asc()).all()
    return [DataSourceOut.model_validate(s) for s in sources]


@router.patch("/data-sources/{source_id}", response_model=DataSourceOut)
def update_data_source(
    source_id: UUID,
    payload: DataSourceToggleRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ds = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    if payload.is_enabled is not None:
        ds.is_enabled = payload.is_enabled
    if payload.is_authorized is not None:
        ds.is_authorized = payload.is_authorized
    if payload.usage_restrictions is not None:
        ds.usage_restrictions = payload.usage_restrictions
    record_audit_log(
        db,
        action="ADMIN_DATA_SOURCE_UPDATED",
        resource_type="data_source",
        resource_id=str(ds.id),
        user_id=admin.id,
        details=payload.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(ds)
    return DataSourceOut.model_validate(ds)


@router.get("/evaluation")
def get_evaluation_runs(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    runs = db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(10).all()
    return [
        {
            "id": str(r.id),
            "benchmark_name": r.benchmark_name,
            "model_comparison": r.model_comparison,
            "relevance_treatment_note": r.relevance_treatment_note,
            "dataset_disclaimer": r.dataset_disclaimer,
            "total_candidates": r.total_candidates,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]


@router.post("/evaluation/run")
def run_evaluation_now(
    reference_profile_id: Optional[UUID] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    run = execute_benchmark_evaluation(db, user_id=admin.id, reference_profile_id=reference_profile_id)
    record_audit_log(
        db,
        action="ADMIN_EVALUATION_RUN",
        resource_type="evaluation_run",
        resource_id=str(run.id),
        user_id=admin.id,
    )
    db.commit()
    return {
        "id": str(run.id),
        "benchmark_name": run.benchmark_name,
        "model_comparison": run.model_comparison,
        "relevance_treatment_note": run.relevance_treatment_note,
        "dataset_disclaimer": run.dataset_disclaimer,
        "total_candidates": run.total_candidates,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/audit-logs", response_model=list[AuditLogOut])
def get_audit_logs(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [AuditLogOut.model_validate(l) for l in logs]
