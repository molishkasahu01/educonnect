from datetime import datetime, timezone
from typing import Any
import httpx
from app.core.config import get_settings
from app.data_sources.base import BaseDataSourceAdapter, is_restricted_social_url, normalize_whitespace
from app.schemas.candidate import NormalizedCandidateRecord


class AuthorizedAPIAdapter(BaseDataSourceAdapter):
    """Adapter for licensed professional data APIs. Never scrapes restricted endpoints."""

    adapter_type = "licensed_api"

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.licensed_data_api_url and settings.licensed_data_api_key)

    def get_status(self) -> dict[str, Any]:
        settings = get_settings()
        configured = self.is_configured()
        blocked = bool(settings.licensed_data_api_url and is_restricted_social_url(settings.licensed_data_api_url))
        missing = []
        if not settings.licensed_data_api_url:
            missing.append("LICENSED_DATA_API_URL")
        if not settings.licensed_data_api_key:
            missing.append("LICENSED_DATA_API_KEY")
        return {
            "configured": configured and not blocked,
            "missing_env_vars": missing,
            "blocked_domain": blocked,
        }

    def fetch_from_configured_api(self, query_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        settings = get_settings()
        if not self.is_configured():
            raise RuntimeError(
                "Licensed professional data API is not configured. "
                "Set LICENSED_DATA_API_URL and LICENSED_DATA_API_KEY."
            )
        if is_restricted_social_url(settings.licensed_data_api_url):
            raise PermissionError("Access to restricted social domains is prohibited by policy.")

        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                settings.licensed_data_api_url,
                headers={"Authorization": f"Bearer {settings.licensed_data_api_key}"},
                params=query_params or {},
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("items") or data.get("results") or data.get("profiles") or data.get("data") or []

    def ingest(
        self,
        payload: list[dict[str, Any]],
        source_name: str = "licensed_data_api",
        dataset_type: str = "REAL_DATA",
    ) -> list[NormalizedCandidateRecord]:
        now = datetime.now(timezone.utc)
        records: list[NormalizedCandidateRecord] = []
        for idx, item in enumerate(payload, start=1):
            name = normalize_whitespace(item.get("name") or item.get("full_name"))
            if not name:
                continue
            src_id = str(item.get("id") or item.get("profile_id") or f"api-{idx}")
            records.append(
                NormalizedCandidateRecord(
                    id=self._deterministic_uuid(source_name, src_id),
                    name=name,
                    linkedin_url=item.get("linkedin_url"),
                    current_role=item.get("current_role") or item.get("headline") or item.get("occupation"),
                    organization=item.get("organization") or item.get("company"),
                    location=item.get("location") or item.get("city"),
                    professional_bio=item.get("professional_bio") or item.get("summary") or item.get("bio"),
                    experience_years=item.get("experience_years"),
                    education_segments=item.get("education_segments") or [],
                    school_indicators=item.get("school_indicators") or [],
                    organizations=item.get("organizations") or [],
                    skills=item.get("skills") or [],
                    influence_indicators=item.get("influence_indicators") or [],
                    source=source_name,
                    source_url=item.get("source_url"),
                    source_record_id=src_id,
                    verification_status="verified",
                    dataset_type=dataset_type,  # type: ignore[arg-type]
                    data_confidence=0.90,
                    usage_restrictions="Licensed API terms apply",
                    last_updated=now,
                )
            )
        return records
