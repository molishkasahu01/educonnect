import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.ai.analyzer import AIProfileAnalyzer
from app.ai.cross_encoder import cross_encoder_reranker
from app.ai.embeddings import embedding_service
from app.core.config import get_settings
from app.data_sources.base import build_normalized_professional_document, normalize_person_name
from app.discovery.deduplicator import is_confident_duplicate
from app.models.discovery import (
    DiscoveryJob,
    DiscoveryResult,
    ModelVersion,
    ProfileEmbedding,
    RankingExplanation,
    RankingScore,
)
from app.models.organization import DataSource
from app.models.profile import CandidateProfile, ProfileIndicator, ProfileSource, ReferenceProfile
from app.ranking.engine import DEFAULT_RANKING_WEIGHTS, HybridRankingEngine
from app.ranking.explainability import build_candidate_explanation
from app.services.real_discovery import fetch_real_candidates_from_providers


def _log_stage(db: Session, job: DiscoveryJob, stage: str, percent: int, detail: str) -> None:
    logs = list(job.stage_logs or [])
    logs.append({
        "stage": stage,
        "progress_percent": percent,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    job.current_stage = stage
    job.progress_percent = percent
    job.stage_logs = logs
    db.commit()


def get_active_ranking_config(db: Session) -> tuple[dict[str, float], str]:
    active_mv = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_type == "ranking", ModelVersion.is_active.is_(True))
        .order_by(ModelVersion.created_at.desc())
        .first()
    )
    if active_mv and isinstance(active_mv.config, dict) and active_mv.config:
        return dict(active_mv.config), active_mv.version
    return dict(DEFAULT_RANKING_WEIGHTS), "hybrid-v1.0"


def execute_discovery_pipeline(db: Session, job_id: UUID) -> DiscoveryJob:
    """Execute the full 10-stage semantic + hybrid ranking discovery workflow."""
    start_ts = time.perf_counter()
    job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
    if not job:
        raise ValueError(f"Discovery job {job_id} not found")

    job.status = "RUNNING"
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    db.commit()

    try:
        # Stage 1: Profile Validation
        ref = db.query(ReferenceProfile).filter(ReferenceProfile.id == job.reference_profile_id).first()
        if not ref or ref.deleted_at is not None:
            raise ValueError("Reference profile not found or deleted")
        _log_stage(db, job, "PROFILE_VALIDATION", 10, "Validated reference profile and permissions")

        # Stage 2 & 3: AI Profile Analysis & Attribute Extraction
        analyzer = AIProfileAnalyzer()
        analysis = ref.analysis_summary
        if not analysis or ref.analysis_status != "ANALYZED":
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
            if analysis["analysis_status"] == "NEEDS_MORE_INFO" and not analysis.get("normalized_document"):
                raise ValueError(analysis.get("compliance_notice") or "Reference profile lacks sufficient information for discovery")
            ref.analysis_summary = analysis
            ref.analysis_status = analysis["analysis_status"]
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
            db.commit()

        _log_stage(db, job, "PROFILE_ANALYSIS", 22, "Completed AI reference profile analysis")
        _log_stage(db, job, "ATTRIBUTE_EXTRACTION", 34, f"Extracted {len(analysis.get('school_indicators', []))} school ecosystem indicators")

        # Stage 4: Embedding Generation
        model_name = embedding_service.get_active_model_name()
        model_ver = embedding_service.get_model_version()
        ref_doc = ref.normalized_document or build_normalized_professional_document(
            full_name=ref.full_name,
            current_role=ref.current_designation,
            organization=ref.current_organization,
            location=ref.location,
            professional_bio=ref.professional_bio,
            career_history=ref.career_history,
            skills=ref.skills,
        )
        ref_hash = embedding_service.compute_doc_hash(ref_doc)
        ref_emb_row = (
            db.query(ProfileEmbedding)
            .filter(
                ProfileEmbedding.reference_profile_id == ref.id,
                ProfileEmbedding.model_name == model_name,
            )
            .first()
        )
        if ref_emb_row and ref_emb_row.document_hash == ref_hash:
            ref_vec = ref_emb_row.embedding
        else:
            ref_vec = embedding_service.encode_text(ref_doc, model_name=model_name)
            if ref_emb_row:
                ref_emb_row.embedding = ref_vec
                ref_emb_row.document_hash = ref_hash
                ref_emb_row.model_version = model_ver
            else:
                db.add(
                    ProfileEmbedding(
                        reference_profile_id=ref.id,
                        model_name=model_name,
                        model_version=model_ver,
                        embedding=ref_vec,
                        document_hash=ref_hash,
                    )
                )
            db.commit()

        job.embedding_model_name = model_name
        _log_stage(db, job, "EMBEDDING_GENERATION", 48, f"Generated {len(ref_vec)}-dim embedding via {model_name}")

        # Stage 5: Strict Real-Data-Only Candidate Retrieval (ZERO synthetic/mock records)
        discovery_mode = (job.discovery_mode or "REAL_DATA").upper()
        selected_sources = [s for s in (job.selected_sources or []) if s]
        filters = job.filters_applied or {}

        base_real_filters = (
            CandidateProfile.deleted_at.is_(None),
            CandidateProfile.is_duplicate_of.is_(None),
            CandidateProfile.verification_status.in_(["verified", "unverified"]),
            CandidateProfile.visibility != "shared_benchmark",
        )

        if discovery_mode == "REAL_DATA":
            provider_diag = fetch_real_candidates_from_providers(
                db=db,
                user_id=job.owner_id,
                reference=ref,
                selected_sources=selected_sources,
                filters=filters,
            )
            job.provider_diagnostics = provider_diag
            _log_stage(
                db,
                job,
                "CANDIDATE_RETRIEVAL",
                55,
                f"Checked real-data providers ({', '.join(provider_diag['providers_checked'])}); fetched {provider_diag['live_fetched_count']} live profiles",
            )
            cand_query = db.query(CandidateProfile).filter(
                *base_real_filters,
                CandidateProfile.dataset_type == "REAL_DATA",
                or_(
                    CandidateProfile.owner_id == job.owner_id,
                    CandidateProfile.visibility == "shared_real",
                ),
            )
            real_adapter_filter = [
                s for s in selected_sources if s in ("licensed_api", "public_directory", "organization_website")
            ]
            if real_adapter_filter and len(real_adapter_filter) < 3:
                matching_cand_ids = (
                    db.query(ProfileSource.candidate_id)
                    .join(DataSource, ProfileSource.data_source_id == DataSource.id)
                    .filter(DataSource.adapter_type.in_(real_adapter_filter))
                )
                cand_query = cand_query.filter(CandidateProfile.id.in_(matching_cand_ids))
        elif discovery_mode == "USER_PROVIDED":
            job.provider_diagnostics = {
                "mode": "USER_PROVIDED",
                "providers_checked": selected_sources or ["user_csv", "manual", "crm"],
                "live_fetched_count": 0,
                "unconfigured_providers": [],
                "errors": [],
            }
            cand_query = db.query(CandidateProfile).filter(
                *base_real_filters,
                CandidateProfile.dataset_type == "USER_PROVIDED",
                CandidateProfile.owner_id == job.owner_id,
            )
        elif discovery_mode == "ALL_AUTHORIZED":
            provider_diag = fetch_real_candidates_from_providers(
                db=db,
                user_id=job.owner_id,
                reference=ref,
                selected_sources=selected_sources,
                filters=filters,
            )
            job.provider_diagnostics = provider_diag
            cand_query = db.query(CandidateProfile).filter(
                *base_real_filters,
                CandidateProfile.dataset_type.in_(["REAL_DATA", "USER_PROVIDED"]),
                or_(
                    CandidateProfile.owner_id == job.owner_id,
                    CandidateProfile.visibility == "shared_real",
                ),
            )
        else:
            raise ValueError(
                f"Unsupported discovery_mode '{discovery_mode}'. Only REAL_DATA, USER_PROVIDED, and ALL_AUTHORIZED are permitted."
            )

        if filters.get("location"):
            cand_query = cand_query.filter(CandidateProfile.location.ilike(f"%{filters['location']}%"))
        if filters.get("verification_status") in ("verified", "unverified"):
            cand_query = cand_query.filter(CandidateProfile.verification_status == filters["verification_status"])
        if filters.get("source"):
            cand_query = cand_query.filter(CandidateProfile.primary_source == filters["source"])

        candidates = cand_query.all()
        if not candidates:
            db.query(DiscoveryResult).filter(DiscoveryResult.discovery_job_id == job.id).delete()
            db.flush()
            elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
            job.total_candidates_evaluated = 0
            job.relevant_candidates_count = 0
            job.processing_time_ms = elapsed_ms
            job.status = "COMPLETED"
            job.completed_at = datetime.now(timezone.utc)
            empty_msg = (
                "No verified or authorized professional profiles were found for this discovery. "
                "Connect an authorized source or import genuine professional records."
            )
            _log_stage(db, job, "RESULTS_PERSISTENCE", 100, empty_msg)
            return job

        # Load/backfill missing embeddings for candidate pool
        cand_ids = [c.id for c in candidates]
        emb_rows = (
            db.query(ProfileEmbedding)
            .filter(
                ProfileEmbedding.candidate_id.in_(cand_ids),
                ProfileEmbedding.model_name == model_name,
            )
            .all()
        )
        emb_map: dict[UUID, list[float]] = {r.candidate_id: r.embedding for r in emb_rows if r.candidate_id}

        missing_cands = [c for c in candidates if c.id not in emb_map]
        if missing_cands:
            docs = [
                c.normalized_document
                or build_normalized_professional_document(
                    full_name=c.full_name,
                    current_role=c.current_role,
                    organization=c.organization_name,
                    location=c.location,
                    professional_bio=c.professional_bio,
                    education_segments=c.education_segments,
                    school_indicators=c.school_indicators,
                    organizations=c.organizations_list,
                    skills=c.skills,
                    influence_indicators=c.influence_indicators,
                )
                for c in missing_cands
            ]
            vecs = embedding_service.encode_batch(docs, model_name=model_name)
            for c, d, v in zip(missing_cands, docs, vecs):
                emb_map[c.id] = v
                db.add(
                    ProfileEmbedding(
                        candidate_id=c.id,
                        model_name=model_name,
                        model_version=model_ver,
                        embedding=v,
                        document_hash=embedding_service.compute_doc_hash(d),
                    )
                )
            db.commit()

        # Vector similarity retrieval (pgvector cosine_distance on Postgres, numpy cosine on SQLite)
        settings = get_settings()
        sem_scores_by_cid: dict[UUID, float] = {}
        if settings.is_postgres:
            pg_rows = (
                db.query(
                    ProfileEmbedding.candidate_id,
                    (1 - ProfileEmbedding.embedding.cosine_distance(ref_vec)).label("cos_sim"),
                )
                .filter(
                    ProfileEmbedding.candidate_id.in_(cand_ids),
                    ProfileEmbedding.model_name == model_name,
                )
                .order_by(ProfileEmbedding.embedding.cosine_distance(ref_vec))
                .all()
            )
            for cid, cos_sim in pg_rows:
                if cid:
                    sem_scores_by_cid[cid] = embedding_service.normalize_cosine_to_100(float(cos_sim))
        else:
            for c in candidates:
                cos_sim = embedding_service.cosine_similarity(ref_vec, emb_map[c.id])
                sem_scores_by_cid[c.id] = embedding_service.normalize_cosine_to_100(cos_sim)

        # Broad candidate pool (top 150 by semantic similarity)
        sorted_pool = sorted(
            candidates,
            key=lambda c: sem_scores_by_cid.get(c.id, 0.0),
            reverse=True,
        )[:150]
        _log_stage(db, job, "CANDIDATE_RETRIEVAL", 62, f"Retrieved {len(sorted_pool)} candidates from {len(candidates)} indexed profiles")

        # Stage 6: Similarity Calculation + Optional Cross-Encoder
        cross_scores_map: dict[UUID, float] = {}
        if cross_encoder_reranker.is_enabled() and sorted_pool:
            top_for_ce = sorted_pool[:40]
            ce_docs = [c.normalized_document or (c.professional_bio or c.current_role or c.full_name) for c in top_for_ce]
            ce_scores = cross_encoder_reranker.score_pairs(ref_doc, ce_docs)
            if ce_scores:
                for c, s in zip(top_for_ce, ce_scores):
                    cross_scores_map[c.id] = s
        _log_stage(db, job, "SIMILARITY_CALCULATION", 74, "Computed semantic cosine similarities")

        # Stage 7: Hybrid Ranking
        weights, rank_version = get_active_ranking_config(db)
        job.weights_snapshot = weights
        job.ranking_model_version = rank_version
        engine = HybridRankingEngine(weights=weights, model_version=rank_version)

        ref_dict = {
            "current_designation": ref.current_designation,
            "professional_bio": f"{ref.professional_bio or ''} {ref.career_history or ''} {ref.education_sector_experience or ''}",
            "experience_years": analysis.get("experience_years"),
            "school_indicators": analysis.get("school_indicators") or [],
            "organizations": analysis.get("organizations") or [],
            "influence_indicators": analysis.get("influence_indicators") or [],
            "skills": ref.skills or [],
        }

        scored_pairs = []
        for cand in sorted_pool:
            cand_dict = {
                "id": cand.id,
                "full_name": cand.full_name,
                "current_role": cand.current_role,
                "organization_name": cand.organization_name,
                "location": cand.location,
                "professional_bio": cand.professional_bio,
                "experience_years": cand.experience_years,
                "education_segments": cand.education_segments,
                "school_indicators": cand.school_indicators,
                "organizations_list": cand.organizations_list,
                "skills": cand.skills,
                "influence_indicators": cand.influence_indicators,
                "primary_source": cand.primary_source,
                "source_record_id": cand.source_record_id,
                "source_url": cand.source_url,
                "linkedin_url": cand.linkedin_url,
                "verification_status": cand.verification_status,
                "dataset_type": cand.dataset_type,
                "data_confidence": cand.data_confidence,
                "data_freshness_days": cand.data_freshness_days,
            }
            comp = engine.score_candidate(
                reference=ref_dict,
                candidate=cand_dict,
                semantic_score_100=sem_scores_by_cid.get(cand.id, 0.0),
                cross_encoder_score=cross_scores_map.get(cand.id),
            )
            scored_pairs.append((cand, cand_dict, comp))

        scored_pairs.sort(key=lambda x: (x[2].relevance_score, x[2].evidence_confidence), reverse=True)
        _log_stage(db, job, "HYBRID_RANKING", 84, f"Ranked {len(scored_pairs)} candidates with {rank_version}")

        # Stage 8: Deduplication across ranked candidates
        deduped_pairs = []
        seen_names: dict[str, list[tuple[dict, list[float]]]] = {}
        for cand, cand_dict, comp in scored_pairs:
            norm_n = normalize_person_name(cand.full_name)
            dup_found = False
            for prev_dict, prev_emb in seen_names.get(norm_n, []):
                is_dup, _c, _why = is_confident_duplicate(prev_dict, cand_dict, prev_emb, emb_map.get(cand.id))
                if is_dup:
                    dup_found = True
                    break
            if not dup_found:
                deduped_pairs.append((cand, cand_dict, comp))
                seen_names.setdefault(norm_n, []).append((cand_dict, emb_map.get(cand.id, [])))

        _log_stage(db, job, "DEDUPLICATION", 91, f"Verified {len(deduped_pairs)} unique candidates after deduplication")

        # Stage 9 & 10: Explanation Generation & Atomic Persistence
        db.query(DiscoveryResult).filter(DiscoveryResult.discovery_job_id == job.id).delete()
        db.flush()

        relevant_count = 0
        for rank_idx, (cand, cand_dict, comp) in enumerate(deduped_pairs, start=1):
            if comp.relevance_tier in ("HIGHLY_RELEVANT", "PARTIALLY_RELEVANT") and comp.relevance_score >= 55.0:
                relevant_count += 1
            res = DiscoveryResult(
                discovery_job_id=job.id,
                candidate_id=cand.id,
                rank_position=rank_idx,
                relevance_score=comp.relevance_score,
                evidence_confidence=comp.evidence_confidence,
                meets_minimum_evidence=comp.meets_minimum_evidence,
                relevance_tier=comp.relevance_tier,
            )
            db.add(res)
            db.flush()

            db.add(
                RankingScore(
                    discovery_result_id=res.id,
                    semantic_similarity=comp.semantic_similarity,
                    school_ecosystem_relevance=comp.school_ecosystem_relevance,
                    professional_role_similarity=comp.professional_role_similarity,
                    experience_similarity=comp.experience_similarity,
                    organization_network_overlap=comp.organization_network_overlap,
                    influence_indicators_score=comp.influence_indicators_score,
                    cross_encoder_score=comp.cross_encoder_score,
                    available_components=comp.available_components,
                    weights_used=comp.weights_used,
                    ranking_model_version=rank_version,
                )
            )

            expl = build_candidate_explanation(cand_dict, comp)
            db.add(
                RankingExplanation(
                    discovery_result_id=res.id,
                    summary_explanation=expl["summary_explanation"],
                    matched_attributes=expl["matched_attributes"],
                    missing_evidence_notes=expl["missing_evidence_notes"],
                    evidence_links=expl["evidence_links"],
                    generated_by=expl["generated_by"],
                )
            )

        _log_stage(db, job, "EXPLANATION_GENERATION", 96, f"Generated evidence-linked explanations for {len(deduped_pairs)} candidates")

        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        job.total_candidates_evaluated = len(deduped_pairs)
        job.relevant_candidates_count = relevant_count
        job.processing_time_ms = elapsed_ms
        job.status = "COMPLETED"
        job.completed_at = datetime.now(timezone.utc)
        _log_stage(db, job, "RESULTS_PERSISTENCE", 100, f"Persisted {len(deduped_pairs)} ranked results in {elapsed_ms}ms")
        return job

    except Exception as exc:
        db.rollback()
        failed_job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
        if failed_job:
            failed_job.status = "FAILED"
            failed_job.error_message = str(exc)
            failed_job.completed_at = datetime.now(timezone.utc)
            logs = list(failed_job.stage_logs or [])
            logs.append({
                "stage": "FAILED",
                "progress_percent": failed_job.progress_percent,
                "detail": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            failed_job.stage_logs = logs
            db.commit()
        raise
