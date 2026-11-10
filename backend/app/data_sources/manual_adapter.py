import uuid
from datetime import datetime, timezone
from app.data_sources.base import BaseDataSourceAdapter, normalize_whitespace
from app.schemas.candidate import ManualCandidateImportRequest, NormalizedCandidateRecord


class ManualProfileAdapter(BaseDataSourceAdapter):
    adapter_type = "manual"

    def ingest(self, payload: ManualCandidateImportRequest, **kwargs) -> list[NormalizedCandidateRecord]:
        src_record_id = f"manual-{uuid.uuid4().hex[:12]}"
        linkedin = normalize_whitespace(payload.linkedin_url) or None

        orgs = list(payload.organizations_list)
        if payload.organization_name and payload.organization_name not in orgs:
            orgs.insert(0, payload.organization_name)

        return [
            NormalizedCandidateRecord(
                id=self._deterministic_uuid(payload.source_name, src_record_id),
                name=normalize_whitespace(payload.full_name),
                linkedin_url=linkedin,
                current_role=normalize_whitespace(payload.current_role) or None,
                organization=normalize_whitespace(payload.organization_name) or None,
                location=normalize_whitespace(payload.location) or None,
                professional_bio=normalize_whitespace(payload.professional_bio) or None,
                experience_years=payload.experience_years,
                education_segments=payload.education_segments,
                school_indicators=payload.school_indicators,
                organizations=orgs,
                skills=payload.skills,
                influence_indicators=payload.influence_indicators,
                source=payload.source_name,
                source_url=normalize_whitespace(payload.source_url) or None,
                source_record_id=src_record_id,
                verification_status=payload.verification_status,
                dataset_type=payload.dataset_type,
                data_confidence=0.85 if payload.verification_status == "verified" else 0.65,
                usage_restrictions=payload.authorization_note,
                last_updated=datetime.now(timezone.utc),
            )
        ]
