from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.ai.analyzer import AIProfileAnalyzer, INFLUENCE_PATTERNS, SCHOOL_ECOSYSTEM_TAXONOMY
from app.ai.embeddings import embedding_service
from app.data_sources.base import (
    build_normalized_professional_document,
    check_candidate_eligibility,
    normalize_org_name,
    normalize_person_name,
)
from app.discovery.deduplicator import is_confident_duplicate
from app.models.organization import DataSource, Organization
from app.models.profile import (
    CandidateProfile,
    ProfileIndicator,
    ProfileSource,
)
from app.models.discovery import ModelVersion, ProfileEmbedding
from app.schemas.candidate import NormalizedCandidateRecord


def _ensure_embedding_model_version(db: Session, model_name: str, model_version: str, dim: int) -> ModelVersion:
    mv = (
        db.query(ModelVersion)
        .filter(
            ModelVersion.name == model_name,
            ModelVersion.model_type == "embedding",
            ModelVersion.version == model_version,
        )
        .first()
    )
    if not mv:
        mv = ModelVersion(
            name=model_name,
            model_type="embedding",
            version=model_version,
            dimension=dim,
            config={"normalize_embeddings": True, "device": "cpu"},
            is_active=True,
        )
        db.add(mv)
        db.flush()
    return mv


def ingest_normalized_records(
    db: Session,
    records: list[NormalizedCandidateRecord],
    owner_id: Optional[UUID] = None,
    visibility: str = "private",
    dataset_type: Optional[str] = None,
    adapter_type: str = "csv",
    authorization_note: Optional[str] = None,
    uploaded_by_user_id: Optional[UUID] = None,
    compute_embeddings: bool = True,
) -> dict:
    """Production candidate ingestion pipeline with normalization, deduplication, provenance, and embeddings."""
    now = datetime.now(timezone.utc)
    analyzer = AIProfileAnalyzer()

    imported_ids: list[UUID] = []
    merged_count = 0
    skipped_count = 0
    warnings: list[str] = []

    # Scope duplicate detection strictly to authorized real/user records owned by or shared with this workspace
    existing_candidates = (
        db.query(CandidateProfile)
        .filter(
            CandidateProfile.deleted_at.is_(None),
            CandidateProfile.verification_status != "synthetic",
            CandidateProfile.dataset_type.in_(["REAL_DATA", "USER_PROVIDED"]),
            or_(CandidateProfile.owner_id == owner_id, CandidateProfile.visibility == "shared_real"),
        )
        .all()
    )
    existing_by_source_key = {
        (c.primary_source, c.source_record_id): c for c in existing_candidates
    }
    existing_by_norm_name: dict[str, list[CandidateProfile]] = {}
    for c in existing_candidates:
        existing_by_norm_name.setdefault(c.normalized_name, []).append(c)

    # Ensure DataSource entries exist
    source_cache: dict[str, DataSource] = {}

    def get_or_create_source(src_name: str, usage_rest: str) -> DataSource:
        if src_name in source_cache:
            return source_cache[src_name]
        ds = db.query(DataSource).filter(DataSource.name == src_name).first()
        if not ds:
            ds = DataSource(
                name=src_name,
                adapter_type=adapter_type,
                description=f"Ingested via {adapter_type} adapter",
                is_authorized=True,
                is_enabled=True,
                usage_restrictions=usage_rest,
                last_sync_at=now,
                record_count=0,
            )
            db.add(ds)
            db.flush()
        source_cache[src_name] = ds
        return ds

    new_candidates_for_embedding: list[tuple[CandidateProfile, str]] = []

    for rec in records:
        eligible, reason = check_candidate_eligibility(rec)
        if not eligible:
            skipped_count += 1
            warnings.append(f"Skipped '{rec.name}' ({rec.source_record_id}): {reason}")
            continue

        ds = get_or_create_source(rec.source, rec.usage_restrictions)
        norm_name = normalize_person_name(rec.name)

        # Duplicate check
        matched_existing: Optional[CandidateProfile] = existing_by_source_key.get(
            (rec.source, rec.source_record_id)
        )
        if not matched_existing and norm_name in existing_by_norm_name:
            cand_dict_new = {
                "full_name": rec.name,
                "linkedin_url": rec.linkedin_url,
                "organization_name": rec.organization,
                "location": rec.location,
                "primary_source": rec.source,
                "source_record_id": rec.source_record_id,
            }
            for existing_c in existing_by_norm_name[norm_name]:
                cand_dict_old = {
                    "full_name": existing_c.full_name,
                    "linkedin_url": existing_c.linkedin_url,
                    "organization_name": existing_c.organization_name,
                    "location": existing_c.location,
                    "primary_source": existing_c.primary_source,
                    "source_record_id": existing_c.source_record_id,
                }
                is_dup, _conf, _why = is_confident_duplicate(cand_dict_old, cand_dict_new)
                if is_dup:
                    matched_existing = existing_c
                    break

        if matched_existing:
            # Merge non-destructively and append source provenance if new source_record_id
            existing_src = (
                db.query(ProfileSource)
                .filter(
                    ProfileSource.candidate_id == matched_existing.id,
                    ProfileSource.source_name == rec.source,
                    ProfileSource.source_record_id == rec.source_record_id,
                )
                .first()
            )
            if not existing_src:
                db.add(
                    ProfileSource(
                        candidate_id=matched_existing.id,
                        data_source_id=ds.id,
                        source_name=rec.source,
                        source_url=rec.source_url,
                        source_record_id=rec.source_record_id,
                        collection_timestamp=now,
                        verification_status=rec.verification_status,
                        data_confidence=rec.data_confidence,
                        data_freshness="current",
                        usage_restrictions=rec.usage_restrictions,
                        record_provenance={"adapter": adapter_type, "merged_into": str(matched_existing.id)},
                        upload_authorization_note=authorization_note,
                        uploaded_by_user_id=uploaded_by_user_id,
                    )
                )
            if not matched_existing.professional_bio and rec.professional_bio:
                matched_existing.professional_bio = rec.professional_bio
            if not matched_existing.current_role and rec.current_role:
                matched_existing.current_role = rec.current_role
            if not matched_existing.organization_name and rec.organization:
                matched_existing.organization_name = rec.organization
            if not matched_existing.location and rec.location:
                matched_existing.location = rec.location
            if not matched_existing.linkedin_url and rec.linkedin_url:
                matched_existing.linkedin_url = rec.linkedin_url
            if not matched_existing.source_url and rec.source_url:
                matched_existing.source_url = rec.source_url
            if matched_existing.experience_years is None and rec.experience_years is not None:
                matched_existing.experience_years = rec.experience_years
            matched_existing.last_updated = now
            merged_count += 1
            imported_ids.append(matched_existing.id)
            continue

        # Organization upsert
        org_obj = None
        if rec.organization:
            norm_org = normalize_org_name(rec.organization)
            if norm_org:
                org_obj = db.query(Organization).filter(Organization.normalized_name == norm_org).first()
                if not org_obj:
                    org_obj = Organization(
                        name=rec.organization,
                        normalized_name=norm_org,
                        org_type="k12_school_ecosystem" if rec.school_indicators else "other",
                        location=rec.location,
                        is_synthetic=False,
                    )
                    db.add(org_obj)
                    db.flush()

        combined_factual = f"{rec.current_role or ''} {rec.organization or ''} {rec.professional_bio or ''}".lower()
        effective_school_inds = list(rec.school_indicators or [])
        if not effective_school_inds:
            for _k, (label, kws) in SCHOOL_ECOSYSTEM_TAXONOMY.items():
                if any(kw in combined_factual for kw in kws):
                    effective_school_inds.append(label)
            if "K-12 Education" not in effective_school_inds and any(
                tok in combined_factual for tok in ("school", "schools", "vidya", "principals", "educare", "podar")
            ):
                effective_school_inds.append("K-12 Education")

        effective_influence = list(rec.influence_indicators or [])
        if not effective_influence:
            for inf_k, inf_kws in INFLUENCE_PATTERNS.items():
                if any(kw in combined_factual for kw in inf_kws):
                    effective_influence.append(inf_k.replace("_", " ").title())

        doc_text = build_normalized_professional_document(
            full_name=rec.name,
            current_role=rec.current_role,
            organization=rec.organization,
            location=rec.location,
            professional_bio=rec.professional_bio,
            education_segments=rec.education_segments,
            school_indicators=effective_school_inds,
            organizations=rec.organizations,
            skills=rec.skills,
            influence_indicators=effective_influence,
        )

        freshness_days = max(0, (now - rec.last_updated).days)
        effective_dataset_type = (
            "REAL_DATA"
            if (dataset_type or rec.dataset_type or "USER_PROVIDED").upper() == "REAL_DATA"
            else "USER_PROVIDED"
        )
        effective_vis = "shared_real" if visibility == "shared_real" else "private"
        cand = CandidateProfile(
            owner_id=owner_id,
            organization_id=org_obj.id if org_obj else None,
            full_name=rec.name,
            normalized_name=norm_name,
            linkedin_url=rec.linkedin_url,
            current_role=rec.current_role,
            organization_name=rec.organization,
            location=rec.location,
            professional_bio=rec.professional_bio,
            experience_years=rec.experience_years,
            education_segments=rec.education_segments,
            school_indicators=effective_school_inds,
            organizations_list=rec.organizations,
            skills=rec.skills,
            influence_indicators=effective_influence,
            normalized_document=doc_text,
            primary_source=rec.source,
            source_url=rec.source_url,
            source_record_id=rec.source_record_id,
            verification_status=rec.verification_status,
            data_confidence=rec.data_confidence,
            data_freshness_days=freshness_days,
            usage_restrictions=rec.usage_restrictions,
            dataset_type=effective_dataset_type,
            visibility=effective_vis,
            last_updated=rec.last_updated,
        )
        db.add(cand)
        db.flush()

        # Provenance record
        db.add(
            ProfileSource(
                candidate_id=cand.id,
                data_source_id=ds.id,
                source_name=rec.source,
                source_url=rec.source_url,
                source_record_id=rec.source_record_id,
                collection_timestamp=now,
                verification_status=rec.verification_status,
                data_confidence=rec.data_confidence,
                data_freshness="recent" if freshness_days <= 90 else "aging",
                usage_restrictions=rec.usage_restrictions,
                record_provenance={
                    "adapter_type": adapter_type,
                    "source_record_id": rec.source_record_id,
                    "dataset_type": effective_dataset_type,
                },
                upload_authorization_note=authorization_note,
                uploaded_by_user_id=uploaded_by_user_id,
            )
        )

        # Structured attribute classification with provenance
        attrs = analyzer.analyze_candidate_attributes(
            full_name=cand.full_name,
            current_role=cand.current_role,
            organization_name=cand.organization_name,
            location=cand.location,
            professional_bio=cand.professional_bio,
            experience_years=cand.experience_years,
            education_segments=cand.education_segments,
            school_indicators=cand.school_indicators,
            organizations_list=cand.organizations_list,
            skills=cand.skills,
            influence_indicators=cand.influence_indicators,
            source_name=cand.primary_source,
            source_record_id=cand.source_record_id,
            verification_status=cand.verification_status,
        )
        for a in attrs:
            db.add(
                ProfileIndicator(
                    candidate_id=cand.id,
                    category=a["category"],
                    attribute_name=a["attribute_name"],
                    attribute_value=a["attribute_value"],
                    evidence_text=a["evidence_text"],
                    source_reference=a["source_reference"],
                    classification_type=a["classification_type"],
                    confidence=a["confidence"],
                )
            )

        ds.record_count = (ds.record_count or 0) + 1
        ds.last_sync_at = now
        existing_by_source_key[(cand.primary_source, cand.source_record_id)] = cand
        existing_by_norm_name.setdefault(norm_name, []).append(cand)
        imported_ids.append(cand.id)
        new_candidates_for_embedding.append((cand, doc_text))

    db.flush()

    if compute_embeddings and new_candidates_for_embedding:
        model_name = embedding_service.get_active_model_name()
        model_ver = embedding_service.get_model_version()
        docs = [d for _, d in new_candidates_for_embedding]
        vectors = embedding_service.encode_batch(docs, model_name=model_name)
        mv = _ensure_embedding_model_version(db, model_name, model_ver, len(vectors[0]))
        for (cand, doc_text), vec in zip(new_candidates_for_embedding, vectors):
            db.add(
                ProfileEmbedding(
                    candidate_id=cand.id,
                    model_version_id=mv.id,
                    model_name=model_name,
                    model_version=model_ver,
                    embedding=vec,
                    document_hash=embedding_service.compute_doc_hash(doc_text),
                )
            )

    db.commit()
    return {
        "imported_count": len(new_candidates_for_embedding),
        "merged_duplicates_count": merged_count,
        "skipped_count": skipped_count,
        "warnings": warnings,
        "candidate_ids": imported_ids,
    }
