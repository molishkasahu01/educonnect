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


class PublicDirectoryAdapter(BaseDataSourceAdapter):
    """Adapter for permitted public school leadership directories (structured JSON/entries)."""

    adapter_type = "public_directory"

    def fetch_url(
        self,
        url: str,
        source_name: str = "public_school_directory",
        limit: int | None = None,
    ) -> list[NormalizedCandidateRecord]:
        items = fetch_permitted_public_url(url)
        if limit and limit > 0:
            items = items[:limit]
        for item in items:
            item.setdefault("source_url", url)
        return self.ingest(items, source_name=source_name, dataset_type="REAL_DATA")

    def ingest(
        self,
        payload: list[dict[str, Any]],
        source_name: str = "public_school_directory",
        usage_restrictions: str = "Public directory terms permit attribution-preserving indexing",
        dataset_type: str = "REAL_DATA",
    ) -> list[NormalizedCandidateRecord]:
        now = datetime.now(timezone.utc)
        records: list[NormalizedCandidateRecord] = []
        for idx, entry in enumerate(payload, start=1):
            source_url = normalize_whitespace(entry.get("directory_url") or entry.get("source_url")) or None
            if is_restricted_social_url(source_url):
                continue

            name = normalize_whitespace(entry.get("name") or entry.get("leader_name"))
            if not name:
                continue
            explicit_id = normalize_whitespace(entry.get("directory_id"))
            if explicit_id:
                src_id = explicit_id
            else:
                digest = hashlib.sha1(f"{source_url or source_name}|{name.lower()}".encode("utf-8")).hexdigest()[:16]
                src_id = f"dir-{digest}"
            org = normalize_whitespace(entry.get("school_name") or entry.get("organization")) or None
            linkedin_url = clean_linkedin_profile_url(entry.get("linkedin_url"))
            records.append(
                NormalizedCandidateRecord(
                    id=self._deterministic_uuid(source_name, src_id),
                    name=name,
                    linkedin_url=linkedin_url,
                    current_role=normalize_whitespace(entry.get("title") or entry.get("role")) or None,
                    organization=org,
                    location=normalize_whitespace(entry.get("city") or entry.get("location")) or None,
                    professional_bio=normalize_whitespace(entry.get("bio") or entry.get("summary")) or None,
                    experience_years=entry.get("experience_years"),
                    education_segments=parse_list_field(entry.get("education_segments") or ["K-12"]),
                    school_indicators=parse_list_field(entry.get("school_indicators")),
                    organizations=parse_list_field(entry.get("organizations") or org),
                    skills=parse_list_field(entry.get("skills")),
                    influence_indicators=parse_list_field(entry.get("influence_indicators")),
                    source=source_name,
                    source_url=source_url,
                    source_record_id=src_id,
                    verification_status="verified" if (source_url and entry.get("verified")) else "unverified",
                    dataset_type=dataset_type,  # type: ignore[arg-type]
                    data_confidence=0.85 if (source_url and entry.get("verified")) else 0.72,
                    usage_restrictions=usage_restrictions,
                    last_updated=now,
                )
            )
        return records
