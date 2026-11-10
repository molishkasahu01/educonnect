import hashlib
from datetime import datetime, timezone
from typing import Any
from app.data_sources.base import (
    BaseDataSourceAdapter,
    clean_linkedin_profile_url,
    fetch_permitted_public_url,
    is_restricted_social_url,
    normalize_whitespace,
    parse_list_field,
)
from app.schemas.candidate import NormalizedCandidateRecord


class OrganizationWebsiteAdapter(BaseDataSourceAdapter):
    """Adapter for official education organization leadership/biography pages where reuse is permitted."""

    adapter_type = "organization_website"

    def fetch_url(
        self,
        url: str,
        source_name: str = "official_org_website",
        limit: int | None = None,
    ) -> list[NormalizedCandidateRecord]:
        items = fetch_permitted_public_url(url)
        if limit and limit > 0:
            items = items[:limit]
        for item in items:
            item.setdefault("page_url", url)
        return self.ingest(items, source_name=source_name, dataset_type="REAL_DATA")

    def ingest(
        self,
        payload: list[dict[str, Any]],
        source_name: str = "official_org_website",
        dataset_type: str = "REAL_DATA",
    ) -> list[NormalizedCandidateRecord]:
        now = datetime.now(timezone.utc)
        records: list[NormalizedCandidateRecord] = []
        for idx, item in enumerate(payload, start=1):
            org_url = normalize_whitespace(item.get("page_url") or item.get("source_url")) or None
            if is_restricted_social_url(org_url):
                continue

            name = normalize_whitespace(item.get("person_name") or item.get("name"))
            if not name:
                continue
            explicit_id = normalize_whitespace(item.get("record_id"))
            if explicit_id:
                src_id = explicit_id
            else:
                digest = hashlib.sha1(f"{org_url or source_name}|{name.lower()}".encode("utf-8")).hexdigest()[:16]
                src_id = f"orgweb-{digest}"
            org = normalize_whitespace(item.get("organization")) or None
            linkedin_url = clean_linkedin_profile_url(item.get("linkedin_url"))
            records.append(
                NormalizedCandidateRecord(
                    id=self._deterministic_uuid(source_name, src_id),
                    name=name,
                    linkedin_url=linkedin_url,
                    current_role=normalize_whitespace(item.get("designation") or item.get("current_role") or item.get("title")) or None,
                    organization=org,
                    location=normalize_whitespace(item.get("location")) or None,
                    professional_bio=normalize_whitespace(item.get("biography") or item.get("bio")) or None,
                    experience_years=item.get("experience_years"),
                    education_segments=parse_list_field(item.get("education_segments")),
                    school_indicators=parse_list_field(item.get("school_indicators")),
                    organizations=parse_list_field(item.get("organizations") or org),
                    skills=parse_list_field(item.get("skills")),
                    influence_indicators=parse_list_field(item.get("influence_indicators")),
                    source=source_name,
                    source_url=org_url,
                    source_record_id=src_id,
                    verification_status="verified" if org_url else "unverified",
                    dataset_type=dataset_type,  # type: ignore[arg-type]
                    data_confidence=0.85 if org_url else 0.65,
                    usage_restrictions="Official organization public biography; attribution required",
                    last_updated=now,
                )
            )
        return records
