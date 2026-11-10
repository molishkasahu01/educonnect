"""Database bootstrap script: initializes default ranking weights and authorized data-source
registry entries, and optionally provisions an initial admin user from environment variables.
Zero synthetic, fictional, or demonstration candidate records are ever inserted.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.discovery import ModelVersion
from app.models.organization import DataSource
from app.models.user import User
from app.ranking.engine import DEFAULT_RANKING_WEIGHTS


def ensure_default_ranking_and_sources(db) -> None:
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

    real_sources = [
        ("user_authorized_csv", "csv", "User-authorized CSV exports with explicit provenance confirmation", True, True),
        ("manual_user_entry", "manual", "Manually entered real professional profiles", True, True),
        ("authorized_crm_export", "crm", "Authorized CRM partner contact exports", True, True),
        ("public_school_directory", "public_directory", "Permitted public education association & conference directories", True, True),
        ("official_org_website", "organization_website", "Permitted official school group & consultancy leadership pages", True, True),
        ("licensed_data_api", "licensed_api", "External licensed professional data API (requires LICENSED_DATA_API_URL & LICENSED_DATA_API_KEY)", False, False),
    ]
    for name, adapter_t, desc, auth, enabled in real_sources:
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
    db.flush()


def ensure_env_admin_user(db) -> bool:
    admin_email = (os.environ.get("EDXSO_ADMIN_EMAIL") or "").strip().lower()
    admin_pw = os.environ.get("EDXSO_ADMIN_PASSWORD") or ""
    if not admin_email or not admin_pw:
        return False
    existing = db.query(User).filter(User.email == admin_email).first()
    if existing:
        return False
    db.add(
        User(
            email=admin_email,
            full_name=os.environ.get("EDXSO_ADMIN_NAME", "EDXSO Administrator"),
            password_hash=hash_password(admin_pw),
            role="ADMIN",
            is_active=True,
        )
    )
    return True


def bootstrap_all() -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_ranking_and_sources(db)
        created_admin = ensure_env_admin_user(db)
        db.commit()
        return {"status": "bootstrapped_real_only", "created_admin": created_admin}
    finally:
        db.close()


if __name__ == "__main__":
    print(bootstrap_all())
