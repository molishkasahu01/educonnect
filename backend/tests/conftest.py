import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Use isolated test DB before importing app settings/engine
TEST_DB_PATH = BACKEND_DIR / "test_edxso.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["TASK_QUEUE_MODE"] = "local"
os.environ["JWT_SECRET_KEY"] = "test-only-edxso-jwt-secret-key-minimum-48-characters-long"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["EDXSO_ENABLE_DEFAULT_PUBLIC_WEB_SOURCES"] = "false"

from app.core.config import get_settings
get_settings.cache_clear()

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models.discovery import ModelVersion
from app.models.organization import DataSource
from app.models.user import User
from app.ranking.engine import DEFAULT_RANKING_WEIGHTS


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "admin@test.edxso").first():
            db.add(
                User(
                    email="admin@test.edxso",
                    full_name="Test Admin",
                    password_hash=hash_password("AdminPass!123"),
                    role="ADMIN",
                    is_active=True,
                )
            )
        if not db.query(ModelVersion).filter(ModelVersion.model_type == "ranking").first():
            db.add(
                ModelVersion(
                    name="edxso_hybrid_ranker",
                    model_type="ranking",
                    version="hybrid-v1.0",
                    config=dict(DEFAULT_RANKING_WEIGHTS),
                    is_active=True,
                )
            )
        for src_name, adapter_t in (
            ("user_authorized_csv", "csv"),
            ("manual_user_entry", "manual"),
            ("public_school_directory", "public_directory"),
            ("official_org_website", "organization_website"),
            ("licensed_data_api", "licensed_api"),
        ):
            if not db.query(DataSource).filter(DataSource.name == src_name).first():
                db.add(
                    DataSource(
                        name=src_name,
                        adapter_type=adapter_t,
                        description=f"Test registry entry for {adapter_t}",
                        is_authorized=(adapter_t != "licensed_api"),
                        is_enabled=(adapter_t != "licensed_api"),
                        usage_restrictions="Authorized test scope",
                    )
                )
        db.commit()
    finally:
        db.close()

    yield

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
