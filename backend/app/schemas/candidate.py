from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.reference import ProfileExperienceOut, ProfileIndicatorOut


class NormalizedCandidateRecord(BaseModel):
    id: UUID
    name: str
    linkedin_url: Optional[str] = None
    current_role: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    professional_bio: Optional[str] = None
    experience_years: Optional[float] = None
    education_segments: list[str] = Field(default_factory=list)
    school_indicators: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    influence_indicators: list[str] = Field(default_factory=list)
    source: str
    source_url: Optional[str] = None
    source_record_id: str
    verification_status: Literal["verified", "unverified"]
    dataset_type: Literal["REAL_DATA", "USER_PROVIDED"] = "USER_PROVIDED"
    data_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    usage_restrictions: str = "Authorized internal evaluation only"
    last_updated: datetime


class ProfileSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_name: str
    source_url: Optional[str] = None
    source_record_id: str
    collection_timestamp: datetime
    verification_status: str
    data_confidence: float
    data_freshness: str
    usage_restrictions: str
    record_provenance: dict[str, Any]
    upload_authorization_note: Optional[str] = None


class CandidateProfileSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    linkedin_url: Optional[str] = None
    current_role: Optional[str] = None
    organization_name: Optional[str] = None
    location: Optional[str] = None
    professional_bio: Optional[str] = None
    experience_years: Optional[float] = None
    education_segments: list[str]
    school_indicators: list[str]
    organizations_list: list[str]
    skills: list[str]
    influence_indicators: list[str]
    primary_source: str
    source_url: Optional[str] = None
    source_record_id: str
    verification_status: str
    data_confidence: float
    data_freshness_days: int
    usage_restrictions: str
    dataset_type: str = "USER_PROVIDED"
    visibility: str
    last_updated: datetime


class CandidateProfileDetailOut(CandidateProfileSummaryOut):
    experiences: list[ProfileExperienceOut] = Field(default_factory=list)
    indicators: list[ProfileIndicatorOut] = Field(default_factory=list)
    sources: list[ProfileSourceOut] = Field(default_factory=list)


class CandidateImportResponse(BaseModel):
    imported_count: int
    merged_duplicates_count: int
    skipped_count: int
    source_name: str
    verification_status: str
    dataset_type: str = "USER_PROVIDED"
    authorization_recorded: bool
    warnings: list[str] = Field(default_factory=list)
    candidate_ids: list[UUID] = Field(default_factory=list)


class ManualCandidateImportRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=512)
    current_role: Optional[str] = None
    organization_name: Optional[str] = None
    location: Optional[str] = None
    professional_bio: Optional[str] = None
    experience_years: Optional[float] = Field(None, ge=0, le=70)
    education_segments: list[str] = Field(default_factory=list)
    school_indicators: list[str] = Field(default_factory=list)
    organizations_list: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    influence_indicators: list[str] = Field(default_factory=list)
    source_name: str = Field(default="manual_user_entry", max_length=128)
    source_url: Optional[str] = None
    verification_status: Literal["verified", "unverified"] = "unverified"
    authorization_confirmed: bool = True
    authorization_note: str = Field(
        default="User-confirmed authorized profile submission",
        max_length=500,
    )
    dataset_type: Literal["REAL_DATA", "USER_PROVIDED"] = "USER_PROVIDED"


class PermittedUrlImportRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=20)
    source_type: Literal["public_directory", "organization_website"] = "organization_website"
    source_name: str = Field(default="official_org_website", max_length=128)
    authorization_confirmed: bool = True
    authorization_note: str = Field(
        default="Permitted public education source collection",
        max_length=500,
    )
