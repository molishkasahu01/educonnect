from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import (
    admin,
    analytics,
    auth,
    candidates,
    discovery,
    exports,
    health,
    lists,
    reference_profiles,
)
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import RateLimitAndSecurityHeadersMiddleware
from app.models.discovery import ModelVersion
from app.models.organization import DataSource
from app.ranking.engine import DEFAULT_RANKING_WEIGHTS
import app.models  # noqa: F401 - register models

settings = get_settings()
configure_logging(debug=settings.debug)
logger = get_logger(__name__)


def _ensure_bootstrap_defaults() -> None:
    """Idempotently initialize active ranking weights & authorized data source rows on empty DBs."""
    db = SessionLocal()
    try:
        mv = (
            db.query(ModelVersion)
            .filter(ModelVersion.model_type == "ranking", ModelVersion.is_active.is_(True))
            .first()
        )
        if not mv:
            db.add(
                ModelVersion(
                    name="edxso_hybrid_ranker",
                    model_type="ranking",
                    version="hybrid-v1.0",
                    config=dict(DEFAULT_RANKING_WEIGHTS),
                    is_active=True,
                )
            )
        default_sources = [
            ("user_authorized_csv", "csv", "User-authorized CSV exports with explicit provenance confirmation", True, True),
            ("manual_user_entry", "manual", "Manually entered real professional profiles", True, True),
            ("authorized_crm_export", "crm", "Authorized CRM partner contact exports", True, True),
            ("public_school_directory", "public_directory", "Permitted public education association & conference directories", True, True),
            ("official_org_website", "organization_website", "Permitted official school group & consultancy leadership pages", True, True),
            ("licensed_data_api", "licensed_api", "External licensed professional data API (requires LICENSED_DATA_API_URL & LICENSED_DATA_API_KEY)", False, False),
        ]
        for name, adapter_t, desc, auth, enabled in default_sources:
            if not db.query(DataSource).filter(DataSource.name == name).first():
                db.add(
                    DataSource(
                        name=name,
                        adapter_type=adapter_t,
                        description=desc,
                        is_authorized=auth,
                        is_enabled=enabled,
                        usage_restrictions="Compliance policy enforced; no unauthorized scraping",
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("edxso_backend_starting", env=settings.app_env, db_postgres=settings.is_postgres)
    if not settings.is_postgres:
        # Ensure local dev/test SQLite schema exists when starting directly
        Base.metadata.create_all(bind=engine)
    _ensure_bootstrap_defaults()
    yield
    logger.info("edxso_backend_shutting_down")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI-powered professional discovery & hybrid ranking platform for the K-12 school education ecosystem.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(RateLimitAndSecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"^https://educonnect-[a-z0-9-]+\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

prefix = settings.api_v1_prefix
app.include_router(health.router, prefix=prefix)
app.include_router(auth.router, prefix=prefix)
app.include_router(reference_profiles.router, prefix=prefix)
app.include_router(discovery.router, prefix=prefix)
app.include_router(exports.router, prefix=prefix)
app.include_router(candidates.router, prefix=prefix)
app.include_router(lists.router, prefix=prefix)
app.include_router(analytics.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
