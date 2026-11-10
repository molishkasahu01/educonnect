from datetime import datetime, timezone
from typing import Any
from app.data_sources.base import BaseDataSourceAdapter, normalize_whitespace, parse_list_field
from app.schemas.candidate import NormalizedCandidateRecord


class CRMAdapter(BaseDataSourceAdapter):
    """Adapter for authorized CRM exports (e.g. HubSpot/Salesforce/Zoho partner contact exports)."""

    adapter_type = "crm"

    def ingest(
        self,
        payload: list[dict[str, Any]],
        source_name: str = "authorized_crm_export",
        dataset_type: str = "USER_PROVIDED",
    ) -> list[NormalizedCandidateRecord]:
        now = datetime.now(timezone.utc)
        records: list[NormalizedCandidateRecord] = []
        for idx, contact in enumerate(payload, start=1):
            full_name = normalize_whitespace(
                contact.get("full_name")
                or f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
            )
            if not full_name:
                continue
            src_id = normalize_whitespace(contact.get("crm_contact_id") or contact.get("id")) or f"crm-{idx}"
            records.append(
                NormalizedCandidateRecord(
                    id=self._deterministic_uuid(source_name, src_id),
                    name=full_name,
                    linkedin_url=normalize_whitespace(contact.get("linkedin_url")) or None,
                    current_role=normalize_whitespace(contact.get("job_title") or contact.get("current_role")) or None,
                    organization=normalize_whitespace(contact.get("account_name") or contact.get("organization")) or None,
                    location=normalize_whitespace(contact.get("city_region") or contact.get("location")) or None,
                    professional_bio=normalize_whitespace(contact.get("notes") or contact.get("bio")) or None,
                    experience_years=contact.get("experience_years"),
                    education_segments=parse_list_field(contact.get("education_segments")),
                    school_indicators=parse_list_field(contact.get("school_indicators")),
                    organizations=parse_list_field(contact.get("affiliated_organizations") or contact.get("account_name")),
                    skills=parse_list_field(contact.get("expertise_tags") or contact.get("skills")),
                    influence_indicators=parse_list_field(contact.get("influence_indicators")),
                    source=source_name,
                    source_url=None,
                    source_record_id=src_id,
                    verification_status="verified" if contact.get("crm_verified") else "unverified",
                    dataset_type=dataset_type,  # type: ignore[arg-type]
                    data_confidence=0.88 if contact.get("crm_verified") else 0.68,
                    usage_restrictions="Internal CRM authorized export; do not redistribute externally",
                    last_updated=now,
                )
            )
        return records
