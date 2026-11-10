from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ReferenceProfileCreate(BaseModel):
    linkedin_url: Optional[str] = Field(None, max_length=512)
    full_name: Optional[str] = Field(None, max_length=255)
    current_designation: Optional[str] = Field(None, max_length=255)
    current_organization: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    professional_bio: Optional[str] = Field(None, max_length=10000)
    career_history: Optional[str] = Field(None, max_length=15000)
    education_sector_experience: Optional[str] = Field(None, max_length=10000)
    skills: list[str] = Field(default_factory=list)
    additional_notes: Optional[str] = Field(None, max_length=10000)


class ProfileIndicatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    attribute_name: str
    attribute_value: str
    evidence_text: str
    source_reference: str
    classification_type: str
    confidence: float
    extraction_timestamp: datetime


class ProfileExperienceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_name: str
    role_title: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    is_current: bool
    description: Optional[str] = None
    classification_type: str
    source_reference: Optional[str] = None


class ReferenceProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    linkedin_url: Optional[str] = None
    full_name: Optional[str] = None
    current_designation: Optional[str] = None
    current_organization: Optional[str] = None
    location: Optional[str] = None
    professional_bio: Optional[str] = None
    career_history: Optional[str] = None
    education_sector_experience: Optional[str] = None
    skills: list[str]
    additional_notes: Optional[str] = None
    normalized_document: Optional[str] = None
    analysis_status: str
    analysis_summary: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    indicators: list[ProfileIndicatorOut] = Field(default_factory=list)
    experiences: list[ProfileExperienceOut] = Field(default_factory=list)


class ReferenceAnalysisResponse(BaseModel):
    reference_profile: ReferenceProfileOut
    compliance_notice: Optional[str] = None
    missing_critical_fields: list[str] = Field(default_factory=list)
    observed_count: int
    ai_derived_count: int
    missing_count: int
