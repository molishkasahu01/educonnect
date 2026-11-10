"""Real professional discovery orchestrator & provider diagnostics.

Coordinates compliance-safe discovery across licensed B2B APIs, permitted public
education & conference speaker directories, official school group & consultancy websites,
CRM exports, and user-authorized datasets. Strictly prohibits synthetic data and
automated scraping/auth-bypass against restricted social networks (linkedin.com, lnkd.in).
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data_sources import (
    AuthorizedAPIAdapter,
    OrganizationWebsiteAdapter,
    PublicDirectoryAdapter,
    is_restricted_social_url,
)
from app.models.organization import DataSource
from app.models.profile import CandidateProfile, ProfileSource, ReferenceProfile
from app.services.ingestion import ingest_normalized_records


PERMITTED_PUBLIC_SOURCES: list[dict[str, Any]] = [
    {
        "source_type": "public_directory",
        "source_name": "Association of Indian Principals — National Council",
        "url": "https://indianprincipals.com/national-council/",
        "limit": 75,
        "authorization_note": "Permitted public principals council directory; attribution-preserving indexing, robots.txt compliant.",
    },
    {
        "source_type": "public_directory",
        "source_name": "EGN Connect X Education Conference Speakers",
        "url": "https://egnconnectx.com/conference-speakers.php",
        "limit": 65,
        "authorization_note": "Permitted public K-12 & education conference speaker roster; attribution-preserving indexing, robots.txt compliant.",
    },
    {
        "source_type": "public_directory",
        "source_name": "The Schools of India Summit — Advisory & Speakers",
        "url": "https://theschoolsofindia.org/summit",
        "limit": 40,
        "authorization_note": "Permitted public K-12 education summit roster; attribution-preserving indexing, robots.txt compliant.",
    },
    {
        "source_type": "organization_website",
        "source_name": "LIFE Educare K-12 Consultancy Leadership",
        "url": "https://lifeeducare.com/team/",
        "limit": 30,
        "authorization_note": "Permitted official K-12 education consultancy team page; attribution-preserving indexing, robots.txt compliant.",
    },
    {
        "source_type": "organization_website",
        "source_name": "Global Schools Group (GIIS) Leadership & Board",
        "url": "https://globalindianschool.org/sg/about/giis-management-and-board",
        "limit": 30,
        "authorization_note": "Permitted official school network leadership page; attribution-preserving indexing, robots.txt compliant.",
    },
    {
        "source_type": "organization_website",
        "source_name": "Pratham Education Foundation Leadership",
        "url": "https://www.pratham.org/about/leadership/",
        "limit": 20,
        "authorization_note": "Permitted official education foundation leadership page; attribution-preserving indexing, robots.txt compliant.",
    },
    {
        "source_type": "organization_website",
        "source_name": "Pratham Education Foundation Board of Trustees",
        "url": "https://www.pratham.org/about/board/",
        "limit": 20,
        "authorization_note": "Permitted official education foundation board page; attribution-preserving indexing, robots.txt compliant.",
    },
]


def get_provider_statuses(db: Session, user_id: UUID) -> dict[str, Any]:
    """Return live environment counts and connection/authorization status of real discovery providers."""
    settings = get_settings()
    counts_rows = (
        db.query(CandidateProfile.dataset_type, func.count(CandidateProfile.id))
        .filter(
            CandidateProfile.deleted_at.is_(None),
            CandidateProfile.is_duplicate_of.is_(None),
            CandidateProfile.verification_status.in_(["verified", "unverified"]),
            CandidateProfile.dataset_type.in_(["REAL_DATA", "USER_PROVIDED"]),
            or_(
                CandidateProfile.owner_id == user_id,
                CandidateProfile.visibility == "shared_real",
            ),
        )
        .group_by(CandidateProfile.dataset_type)
        .all()
    )
    env_counts = {
        "REAL_DATA": 0,
        "USER_PROVIDED": 0,
    }
    for dt, cnt in counts_rows:
        if dt in env_counts:
            env_counts[dt] = int(cnt)

    api_adapter = AuthorizedAPIAdapter()
    api_status = api_adapter.get_status()
    configured_urls = [
        u.strip()
        for u in os.environ.get("EDXSO_PERMITTED_SOURCE_URLS", "").split(",")
        if u.strip()
    ]

    adapter_by_source = {
        ds.name: ds.adapter_type
        for ds in db.query(DataSource.name, DataSource.adapter_type).all()
    }
    real_by_source = {
        src: int(cnt)
        for src, cnt in (
            db.query(CandidateProfile.primary_source, func.count(CandidateProfile.id))
            .filter(
                CandidateProfile.deleted_at.is_(None),
                CandidateProfile.is_duplicate_of.is_(None),
                CandidateProfile.verification_status.in_(["verified", "unverified"]),
                CandidateProfile.dataset_type == "REAL_DATA",
                or_(
                    CandidateProfile.owner_id == user_id,
                    CandidateProfile.visibility == "shared_real",
                ),
            )
            .group_by(CandidateProfile.primary_source)
            .all()
        )
    }

    dir_count = sum(
        cnt
        for s, cnt in real_by_source.items()
        if adapter_by_source.get(s) == "public_directory"
        or any(k in s.lower() for k in ("directory", "speaker", "association", "principals", "summit"))
    )
    web_count = sum(
        cnt
        for s, cnt in real_by_source.items()
        if adapter_by_source.get(s) == "organization_website"
        or any(k in s.lower() for k in ("org", "website", "school", "consultancy", "educare", "pratham"))
    )

    default_web_n = sum(1 for s in PERMITTED_PUBLIC_SOURCES if s["source_type"] == "organization_website")
    default_dir_n = sum(1 for s in PERMITTED_PUBLIC_SOURCES if s["source_type"] == "public_directory")
    web_ready = bool(configured_urls) or web_count > 0 or settings.edxso_enable_default_public_web_sources
    dir_ready = bool(configured_urls) or dir_count > 0 or settings.edxso_enable_default_public_web_sources

    providers = [
        {
            "id": "organization_website",
            "name": "Official School & Consultancy Websites",
            "adapter_type": "organization_website",
            "environment": "REAL_DATA",
            "configured": web_ready,
            "can_run": True,
            "status_label": (
                f"{web_count} Indexed Profile(s)"
                if web_count > 0
                else (
                    f"{len(configured_urls)} Configured Permitted URL(s)"
                    if configured_urls
                    else (
                        f"Ready ({default_web_n} Permitted Official Websites)"
                        if settings.edxso_enable_default_public_web_sources
                        else "Ready (Supply Permitted Website URLs)"
                    )
                )
            ),
            "record_count": web_count,
            "requires_credentials": False,
            "missing_requirements": [],
            "compliance_note": (
                "Collects leadership & faculty biographies from permitted school websites, school group "
                "pages, and education consultancies respecting robots.txt and JSON-LD/HTML terms."
            ),
        },
        {
            "id": "public_directory",
            "name": "Permitted Education & Conference Speaker Directories",
            "adapter_type": "public_directory",
            "environment": "REAL_DATA",
            "configured": dir_ready,
            "can_run": True,
            "status_label": (
                f"{dir_count} Indexed Profile(s)"
                if dir_count > 0
                else (
                    f"{len(configured_urls)} Configured Directory URL(s)"
                    if configured_urls
                    else (
                        f"Ready ({default_dir_n} Permitted Education Directories)"
                        if settings.edxso_enable_default_public_web_sources
                        else "Ready (Supply Permitted Directory URLs)"
                    )
                )
            ),
            "record_count": dir_count,
            "requires_credentials": False,
            "missing_requirements": [],
            "compliance_note": (
                "Indexes permitted public education association directories and conference speaker rosters "
                "with full source URL attribution."
            ),
        },
        {
            "id": "licensed_api",
            "name": "Licensed Professional Data API",
            "adapter_type": "licensed_api",
            "environment": "REAL_DATA",
            "configured": api_status["configured"],
            "can_run": api_status["configured"],
            "status_label": (
                "Connected"
                if api_status["configured"]
                else ("Blocked Domain" if api_status["blocked_domain"] else "Credentials Required")
            ),
            "record_count": real_by_source.get("licensed_data_api", 0),
            "requires_credentials": True,
            "missing_requirements": api_status["missing_env_vars"],
            "compliance_note": (
                "Connect a licensed B2B professional data API endpoint. Automated LinkedIn scraping "
                "or access-control bypass is blocked."
            ),
        },
        {
            "id": "user_csv",
            "name": "Authorized CSV, CRM Exports & Manual Entries",
            "adapter_type": "csv",
            "environment": "USER_PROVIDED",
            "configured": env_counts["USER_PROVIDED"] > 0,
            "can_run": env_counts["USER_PROVIDED"] > 0,
            "status_label": (
                f"{env_counts['USER_PROVIDED']} Uploaded Profile(s) Ready"
                if env_counts["USER_PROVIDED"] > 0
                else "No Uploaded Profiles Yet"
            ),
            "record_count": env_counts["USER_PROVIDED"],
            "requires_credentials": False,
            "missing_requirements": [] if env_counts["USER_PROVIDED"] > 0 else ["Import authorized CSV/CRM export or manual entry"],
            "compliance_note": (
                "Workspace-isolated genuine CSV/CRM exports and manually entered records with explicit "
                "authorization confirmation."
            ),
        },
    ]

    return {
        "environment_counts": env_counts,
        "providers": providers,
        "compliance_policy": {
            "automated_linkedin_scraping_allowed": False,
            "blocked_domains": ["linkedin.com", "lnkd.in"],
            "summary": (
                "EduConnect operates exclusively on real, traceable professional records. "
                "Automated LinkedIn scraping or auth-wall bypass is strictly prohibited; real LinkedIn URLs "
                "enter only where legitimately published on permitted official websites/directories, via "
                "authorized CSV/CRM exports, or through a licensed professional data API."
            ),
        },
    }


def fetch_real_candidates_from_providers(
    db: Session,
    user_id: UUID,
    reference: ReferenceProfile,
    selected_sources: list[str],
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute live retrieval from configured real-data sources before database ranking.

    Never generates synthetic profiles, fake identities, or fallback placeholders.
    """
    filters = filters or {}
    requested = {s for s in selected_sources if s in ("licensed_api", "public_directory", "organization_website")}
    if not requested:
        requested = {"licensed_api", "public_directory", "organization_website"}

    diagnostics: dict[str, Any] = {
        "providers_checked": sorted(requested),
        "live_fetched_count": 0,
        "unconfigured_providers": [],
        "errors": [],
        "source_results": {},
    }

    if "licensed_api" in requested:
        api_adapter = AuthorizedAPIAdapter()
        if not api_adapter.is_configured():
            diagnostics["unconfigured_providers"].append("licensed_api")
            diagnostics["source_results"]["licensed_api"] = {
                "status": "unconfigured",
                "message": "Set LICENSED_DATA_API_URL and LICENSED_DATA_API_KEY to enable licensed API discovery.",
                "fetched": 0,
            }
        else:
            try:
                query_params = {
                    "role": reference.current_designation or "",
                    "location": reference.location or "",
                    "keywords": ",".join((reference.skills or [])[:5]),
                }
                raw_items = api_adapter.fetch_from_configured_api(query_params=query_params)
                norm_records = api_adapter.ingest(raw_items, source_name="licensed_data_api", dataset_type="REAL_DATA")
                if norm_records:
                    ing = ingest_normalized_records(
                        db=db,
                        records=norm_records,
                        owner_id=user_id,
                        visibility="private",
                        dataset_type="REAL_DATA",
                        adapter_type="licensed_api",
                        authorization_note="Live query against configured LICENSED_DATA_API_URL",
                        uploaded_by_user_id=user_id,
                        compute_embeddings=True,
                    )
                    fetched_n = ing["imported_count"] + ing["merged_duplicates_count"]
                    diagnostics["live_fetched_count"] += fetched_n
                    diagnostics["source_results"]["licensed_api"] = {"status": "ok", "fetched": fetched_n}
                else:
                    diagnostics["source_results"]["licensed_api"] = {"status": "empty", "fetched": 0}
            except Exception as exc:
                diagnostics["errors"].append(f"licensed_api: {exc}")
                diagnostics["source_results"]["licensed_api"] = {
                    "status": "error",
                    "message": str(exc),
                    "fetched": 0,
                }

    settings = get_settings()
    raw_urls = filters.get("permitted_urls") or []
    if isinstance(raw_urls, str):
        permitted_urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
    else:
        permitted_urls = [str(u).strip() for u in raw_urls if str(u).strip()]

    for env_url in os.environ.get("EDXSO_PERMITTED_SOURCE_URLS", "").split(","):
        cleaned = env_url.strip()
        if cleaned and cleaned not in permitted_urls:
            permitted_urls.append(cleaned)

    fetch_targets: list[dict[str, Any]] = []
    for url in permitted_urls:
        if is_restricted_social_url(url):
            diagnostics["errors"].append(f"Blocked restricted domain URL: {url}")
            continue
        use_org = "organization_website" in requested and "public_directory" not in requested
        adapter_t = "organization_website" if use_org else "public_directory"
        fetch_targets.append(
            {
                "source_type": adapter_t,
                "source_name": "official_org_website" if use_org else "public_school_directory",
                "url": url,
                "limit": None,
                "visibility": "private",
                "authorization_note": f"Permitted live URL fetch: {url}",
            }
        )

    # Curated verified K-12 public education directories & official websites (when enabled and requested)
    if (
        settings.edxso_enable_default_public_web_sources
        and ("public_directory" in requested or "organization_website" in requested)
    ):
        freshness_cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
        force_refresh = bool(filters.get("force_refresh"))
        for curated in PERMITTED_PUBLIC_SOURCES:
            if curated["source_type"] not in requested:
                continue
            existing_ds = (
                db.query(DataSource)
                .filter(DataSource.name == curated["source_name"])
                .first()
            )
            last_sync = existing_ds.last_sync_at if existing_ds else None
            if last_sync is not None and last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            if (
                not force_refresh
                and existing_ds is not None
                and existing_ds.record_count > 0
                and last_sync is not None
                and last_sync >= freshness_cutoff
            ):
                diagnostics["source_results"][curated["url"]] = {
                    "status": "cached_live",
                    "fetched": 0,
                    "indexed_count": existing_ds.record_count,
                }
                continue
            fetch_targets.append(
                {
                    **curated,
                    "visibility": "shared_real",
                }
            )

    def _fetch_target(spec: dict[str, Any]) -> tuple[dict[str, Any], list[Any], str | None]:
        try:
            if spec["source_type"] == "organization_website":
                recs = OrganizationWebsiteAdapter().fetch_url(
                    spec["url"],
                    source_name=spec["source_name"],
                    limit=spec.get("limit"),
                )
            else:
                recs = PublicDirectoryAdapter().fetch_url(
                    spec["url"],
                    source_name=spec["source_name"],
                    limit=spec.get("limit"),
                )
            return spec, recs, None
        except Exception as exc:
            return spec, [], str(exc)

    if fetch_targets:
        workers = min(6, len(fetch_targets))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fetched_batches = list(executor.map(_fetch_target, fetch_targets))

        for spec, recs, err in fetched_batches:
            url = spec["url"]
            if err:
                diagnostics["errors"].append(f"{url}: {err}")
                diagnostics["source_results"][url] = {"status": "error", "message": err, "fetched": 0}
                continue
            if recs:
                ing = ingest_normalized_records(
                    db=db,
                    records=recs,
                    owner_id=user_id,
                    visibility=spec["visibility"],
                    dataset_type="REAL_DATA",
                    adapter_type=spec["source_type"],
                    authorization_note=spec["authorization_note"],
                    uploaded_by_user_id=user_id,
                    compute_embeddings=True,
                )
                cnt = ing["imported_count"] + ing["merged_duplicates_count"]
                ds_obj = db.query(DataSource).filter(DataSource.name == spec["source_name"]).first()
                if ds_obj:
                    ds_obj.last_sync_at = datetime.now(timezone.utc)
                    ds_obj.record_count = (
                        db.query(func.count(func.distinct(ProfileSource.candidate_id)))
                        .filter(ProfileSource.source_name == spec["source_name"])
                        .scalar()
                        or 0
                    )
                    db.flush()
                diagnostics["live_fetched_count"] += cnt
                diagnostics["source_results"][url] = {"status": "ok", "fetched": cnt}
            else:
                diagnostics["source_results"][url] = {"status": "empty", "fetched": 0}

    return diagnostics
