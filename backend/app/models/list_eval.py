import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.types import GUID, PortableJSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SavedList(Base):
    __tablename__ = "saved_lists"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profiles: Mapped[list["SavedListProfile"]] = relationship(back_populates="saved_list", cascade="all, delete-orphan")


class SavedListProfile(Base):
    __tablename__ = "saved_list_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    saved_list_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("saved_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    discovery_job_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("discovery_jobs.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    saved_list: Mapped["SavedList"] = relationship(back_populates="profiles")

    __table_args__ = (
        UniqueConstraint("saved_list_id", "candidate_id", name="uq_saved_list_candidate"),
    )


class BenchmarkLabel(Base):
    __tablename__ = "benchmark_labels"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reference_key: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_source_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    labeled_by: Mapped[str] = mapped_column(String(128), nullable=False, default="benchmark_curator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("benchmark_name", "candidate_source_record_id", name="uq_benchmark_candidate_record"),
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_comparison: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    relevance_treatment_note: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
