import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.types import EmbeddingVector, GUID, PortableJSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "model_type", "version", name="uq_model_name_type_version"),
    )


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    reference_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("reference_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(384), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_profile_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("reference_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="QUEUED")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_logs: Mapped[list[dict]] = mapped_column(PortableJSON(), nullable=False, default=list)
    total_candidates_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relevant_candidates_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ranking_model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="hybrid-v1.0")
    embedding_model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="BAAI/bge-small-en-v1.5")
    discovery_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="REAL_DATA", index=True)
    selected_sources: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    provider_diagnostics: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    weights_snapshot: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    filters_applied: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class DiscoveryResult(Base):
    __tablename__ = "discovery_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    discovery_job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    evidence_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    meets_minimum_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    relevance_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    job: Mapped["DiscoveryJob"] = relationship(back_populates="results")
    ranking_score: Mapped["RankingScore | None"] = relationship(back_populates="result", uselist=False, cascade="all, delete-orphan")
    explanation: Mapped["RankingExplanation | None"] = relationship(back_populates="result", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("discovery_job_id", "candidate_id", name="uq_job_candidate"),
        Index("ix_discovery_result_job_rank", "discovery_job_id", "rank_position"),
    )


class RankingScore(Base):
    __tablename__ = "ranking_scores"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    discovery_result_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_results.id", ondelete="CASCADE"), unique=True, nullable=False)
    semantic_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    school_ecosystem_relevance: Mapped[float] = mapped_column(Float, nullable=False)
    professional_role_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    experience_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    organization_network_overlap: Mapped[float] = mapped_column(Float, nullable=False)
    influence_indicators_score: Mapped[float] = mapped_column(Float, nullable=False)
    cross_encoder_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    available_components: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    weights_used: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    ranking_model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    result: Mapped["DiscoveryResult"] = relationship(back_populates="ranking_score")


class RankingExplanation(Base):
    __tablename__ = "ranking_explanations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    discovery_result_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_results.id", ondelete="CASCADE"), unique=True, nullable=False)
    summary_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    matched_attributes: Mapped[list[dict]] = mapped_column(PortableJSON(), nullable=False, default=list)
    missing_evidence_notes: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    evidence_links: Mapped[list[dict]] = mapped_column(PortableJSON(), nullable=False, default=list)
    generated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="deterministic_evidence_engine")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    result: Mapped["DiscoveryResult"] = relationship(back_populates="explanation")
