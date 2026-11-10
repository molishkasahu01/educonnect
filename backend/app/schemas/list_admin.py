from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.candidate import CandidateProfileSummaryOut


class SavedListCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class SavedListAddCandidate(BaseModel):
    candidate_id: UUID
    discovery_job_id: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=2000)


class SavedListItemOut(BaseModel):
    id: UUID
    candidate_id: UUID
    discovery_job_id: Optional[UUID] = None
    notes: Optional[str] = None
    added_at: datetime
    candidate: CandidateProfileSummaryOut


class SavedListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    candidate_count: int = 0
    items: list[SavedListItemOut] = Field(default_factory=list)


class RankingWeightsConfig(BaseModel):
    semantic_similarity: float = Field(0.30, ge=0.0, le=1.0)
    school_ecosystem_relevance: float = Field(0.25, ge=0.0, le=1.0)
    professional_role_similarity: float = Field(0.15, ge=0.0, le=1.0)
    experience_similarity: float = Field(0.10, ge=0.0, le=1.0)
    organization_network_overlap: float = Field(0.10, ge=0.0, le=1.0)
    influence_indicators_score: float = Field(0.10, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self):
        total = (
            self.semantic_similarity
            + self.school_ecosystem_relevance
            + self.professional_role_similarity
            + self.experience_similarity
            + self.organization_network_overlap
            + self.influence_indicators_score
        )
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Ranking weights must sum to 1.0 (got {total:.4f})")
        return self


class ModelConfigUpdate(BaseModel):
    embedding_model_name: Optional[str] = Field(None, min_length=3, max_length=128)
    cross_encoder_enabled: Optional[bool] = None
    cross_encoder_model_name: Optional[str] = Field(None, min_length=3, max_length=128)


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    adapter_type: str
    description: Optional[str] = None
    base_url: Optional[str] = None
    is_authorized: bool
    is_enabled: bool
    usage_restrictions: str
    retention_policy_days: int
    last_sync_at: Optional[datetime] = None
    record_count: int
    created_at: datetime


class DataSourceToggleRequest(BaseModel):
    is_enabled: Optional[bool] = None
    is_authorized: Optional[bool] = None
    usage_restrictions: Optional[str] = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: dict[str, Any]
    ip_address: Optional[str] = None
    created_at: datetime
