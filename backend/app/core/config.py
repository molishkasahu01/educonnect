from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Normalize Render/cloud postgres:// URLs into SQLAlchemy's postgresql+psycopg2:// scheme."""
    raw = (url or "").strip()
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://") :]
    return raw


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "EduConnect School Influencer Intelligence"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api"

    # Auth & Security
    jwt_secret_key: str = Field(
        default="edxso-dev-only-secret-change-in-production-48chars-min-key"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    rate_limit_per_minute: int = 120

    # CORS
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3010,http://127.0.0.1:3010"
    )
    frontend_host: str = ""

    # Database
    database_url: str = "sqlite:///./edxso_local.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(value)

    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    task_queue_mode: str = "local"  # "celery" or "local"

    # AI / ML
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    cross_encoder_enabled: bool = False
    cross_encoder_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Optional external LLM enrichment
    llm_provider: str = "none"
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Optional licensed data API & permitted public web source discovery
    licensed_data_api_url: str = ""
    licensed_data_api_key: str = ""
    edxso_enable_default_public_web_sources: bool = True

    # Uploads & Retention
    max_upload_size_mb: int = 10
    data_retention_days: int = 365

    @property
    def cors_origin_list(self) -> List[str]:
        origins: list[str] = []
        for raw in self.cors_origins.split(","):
            val = raw.strip().rstrip("/")
            if not val:
                continue
            if not val.startswith(("http://", "https://")):
                origins.append(f"https://{val}")
            else:
                origins.append(val)
        if self.frontend_host.strip():
            host = self.frontend_host.strip().rstrip("/")
            origin = host if host.startswith(("http://", "https://")) else f"https://{host}"
            if origin not in origins:
                origins.append(origin)
        return origins

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
