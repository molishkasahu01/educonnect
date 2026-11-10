from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.candidate import CandidateProfileSummaryOut


class DiscoveryCreateRequest(BaseModel):
    reference_profile_id: UUID
    discovery_mode: Literal["REAL_DATA", "USER_PROVIDED", "ALL_AUTHORIZED"] = "REAL_DATA"
    selected_sources: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None, max_length=128)
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=50, ge=5, le=200)


class DiscoveryJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    reference_profile_id: UUID
    status: str
    current_stage: str
    progress_percent: int
    stage_logs: list[dict[str, Any]]
    total_candidates_evaluated: int
    relevant_candidates_count: int
    processing_time_ms: Optional[int] = None
    ranking_model_version: str
    embedding_model_name: str
    discovery_mode: str = "REAL_DATA"
    selected_sources: list[str] = Field(default_factory=list)
    provider_diagnostics: dict[str, Any] = Field(default_factory=dict)
    weights_snapshot: dict[str, Any]
    filters_applied: dict[str, Any]
    error_message: Optional[str] = None
    retry_count: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RankingScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    semantic_similarity: float
    school_ecosystem_relevance: float
    professional_role_similarity: float
    experience_similarity: float
    organization_network_overlap: float
    influence_indicators_score: float
    cross_encoder_score: Optional[float] = None
    available_components: dict[str, Any]
    weights_used: dict[str, Any]
    ranking_model_version: str


class RankingExplanationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary_explanation: str
    matched_attributes: list[dict[str, Any]]
    missing_evidence_notes: list[str]
    evidence_links: list[dict[str, Any]]
    generated_by: str


class DiscoveryResultItemOut(BaseModel):
    id: UUID
    rank_position: int
    relevance_score: float
    evidence_confidence: float
    meets_minimum_evidence: bool
    relevance_tier: str
    candidate: CandidateProfileSummaryOut
    ranking_score: RankingScoreOut
    explanation: RankingExplanationOut


class DiscoveryResultsPageOut(BaseModel):
    job: DiscoveryJobOut
    reference_profile_summary: dict[str, Any]
    dataset_provenance_summary: dict[str, int]
    discovery_mode: str = "REAL_DATA"
    selected_sources: list[str] = Field(default_factory=list)
    provider_diagnostics: dict[str, Any] = Field(default_factory=dict)
    empty_state_message: Optional[str] = None
    total_matched: int
    page: int
    page_size: int
    items: list[DiscoveryResultItemOut]
