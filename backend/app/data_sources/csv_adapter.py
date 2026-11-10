import csv
import io
from datetime import datetime, timezone
from typing import Any
from app.data_sources.base import (
    BaseDataSourceAdapter,
    normalize_whitespace,
    parse_list_field,
)
from app.schemas.candidate import NormalizedCandidateRecord


class CSVAdapter(BaseDataSourceAdapter):
    adapter_type = "csv"

    def ingest(
        self,
        payload: str | bytes,
        source_name: str = "authorized_csv_upload",
        default_verification_status: str = "unverified",
        usage_restrictions: str = "User-authorized CSV upload; internal discovery use only",
        dataset_type: str | None = None,
    ) -> list[NormalizedCandidateRecord]:
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
        reader = csv.DictReader(io.StringIO(text))
        records: list[NormalizedCandidateRecord] = []
        now = datetime.now(timezone.utc)

        for idx, row in enumerate(reader, start=1):
            norm_row = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
            full_name = normalize_whitespace(
                norm_row.get("full_name") or norm_row.get("name") or ""
            )
            if not full_name:
                continue

            ver_status = normalize_whitespace(
                norm_row.get("verification_status") or default_verification_status
            ).lower()
            if ver_status == "synthetic":
                # Strictly prohibit synthetic records in real-data EDXSO
                continue
            if ver_status not in ("verified", "unverified"):
                ver_status = default_verification_status if default_verification_status in ("verified", "unverified") else "unverified"

            raw_linkedin = normalize_whitespace(norm_row.get("linkedin_url")) or None

            exp_raw = normalize_whitespace(norm_row.get("experience_years"))
            exp_years: float | None = None
            if exp_raw:
                try:
                    exp_years = float(exp_raw)
                except ValueError:
                    exp_years = None

            conf_raw = normalize_whitespace(norm_row.get("data_confidence"))
            try:
                data_conf = float(conf_raw) if conf_raw else (0.9 if ver_status == "verified" else 0.7)
            except ValueError:
                data_conf = 0.7
            data_conf = max(0.0, min(1.0, data_conf))

            src_name = normalize_whitespace(norm_row.get("source")) or source_name
            src_record_id = normalize_whitespace(
                norm_row.get("source_record_id") or norm_row.get("record_id") or f"{src_name}-{idx}"
            )
            src_url = normalize_whitespace(norm_row.get("source_url")) or None

            last_updated_str = normalize_whitespace(norm_row.get("last_updated"))
            last_updated = now
            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
                    if last_updated.tzinfo is None:
                        last_updated = last_updated.replace(tzinfo=timezone.utc)
                except ValueError:
                    last_updated = now

            records.append(
                NormalizedCandidateRecord(
                    id=self._deterministic_uuid(src_name, src_record_id),
                    name=full_name,
                    linkedin_url=raw_linkedin,
                    current_role=normalize_whitespace(norm_row.get("current_role") or norm_row.get("role")) or None,
                    organization=normalize_whitespace(norm_row.get("organization") or norm_row.get("organization_name")) or None,
                    location=normalize_whitespace(norm_row.get("location")) or None,
                    professional_bio=normalize_whitespace(norm_row.get("professional_bio") or norm_row.get("bio")) or None,
                    experience_years=exp_years,
                    education_segments=parse_list_field(norm_row.get("education_segments")),
                    school_indicators=parse_list_field(norm_row.get("school_indicators")),
                    organizations=parse_list_field(norm_row.get("organizations") or norm_row.get("organizations_list")),
                    skills=parse_list_field(norm_row.get("skills")),
                    influence_indicators=parse_list_field(norm_row.get("influence_indicators")),
                    source=src_name,
                    source_url=src_url,
                    source_record_id=src_record_id,
                    verification_status=ver_status,  # type: ignore[arg-type]
                    dataset_type=(
                        "REAL_DATA" if (dataset_type or "").upper() == "REAL_DATA" else "USER_PROVIDED"
                    ),  # type: ignore[arg-type]
                    data_confidence=data_conf,
                    usage_restrictions=normalize_whitespace(norm_row.get("usage_restrictions")) or usage_restrictions,
                    last_updated=last_updated,
                )
            )
        return records
