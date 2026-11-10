import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.types import GUID, PortableJSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReferenceProfile(Base):
    __tablename__ = "reference_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    professional_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    career_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_sector_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    additional_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    analysis_summary: Mapped[dict | None] = mapped_column(PortableJSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    indicators: Mapped[list["ProfileIndicator"]] = relationship(
        back_populates="reference_profile",
        cascade="all, delete-orphan",
        foreign_keys="ProfileIndicator.reference_profile_id",
    )
    experiences: Mapped[list["ProfileExperience"]] = relationship(
        back_populates="reference_profile",
        cascade="all, delete-orphan",
        foreign_keys="ProfileExperience.reference_profile_id",
    )


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    current_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    professional_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)

    education_segments: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    school_indicators: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    organizations_list: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    skills: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    influence_indicators: Mapped[list[str]] = mapped_column(PortableJSON(), nullable=False, default=list)
    normalized_document: Mapped[str | None] = mapped_column(Text, nullable=True)

    primary_source: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified", index=True)
    data_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    data_freshness_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_restrictions: Mapped[str] = mapped_column(Text, nullable=False, default="Internal evaluation only")
    dataset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="USER_PROVIDED", index=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private", index=True)
    is_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="SET NULL"), nullable=True)

    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    experiences: Mapped[list["ProfileExperience"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        foreign_keys="ProfileExperience.candidate_id",
    )
    indicators: Mapped[list["ProfileIndicator"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        foreign_keys="ProfileIndicator.candidate_id",
    )
    sources: Mapped[list["ProfileSource"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_candidate_visibility_deleted", "visibility", "deleted_at"),
        Index("ix_candidate_source_record", "primary_source", "source_record_id"),
    )


class ProfileExperience(Base):
    __tablename__ = "profile_experiences"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    reference_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("reference_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_type: Mapped[str] = mapped_column(String(48), nullable=False, default="DIRECTLY_OBSERVED")
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    candidate: Mapped["CandidateProfile | None"] = relationship(back_populates="experiences", foreign_keys=[candidate_id])
    reference_profile: Mapped["ReferenceProfile | None"] = relationship(back_populates="experiences", foreign_keys=[reference_profile_id])


class ProfileIndicator(Base):
    __tablename__ = "profile_indicators"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    reference_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("reference_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attribute_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attribute_value: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    classification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    candidate: Mapped["CandidateProfile | None"] = relationship(back_populates="indicators", foreign_keys=[candidate_id])
    reference_profile: Mapped["ReferenceProfile | None"] = relationship(back_populates="indicators", foreign_keys=[reference_profile_id])


class ProfileSource(Base):
    __tablename__ = "profile_sources"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    collection_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    data_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    data_freshness: Mapped[str] = mapped_column(String(64), nullable=False, default="recent")
    usage_restrictions: Mapped[str] = mapped_column(Text, nullable=False)
    record_provenance: Mapped[dict] = mapped_column(PortableJSON(), nullable=False, default=dict)
    upload_authorization_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="sources")
