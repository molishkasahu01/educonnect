from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.workers.tasks import get_worker_health

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    settings = get_settings()
    db_ok = False
    db_dialect = "unknown"
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        db_dialect = db.bind.dialect.name if db.bind else "unknown"
    except Exception:
        db_ok = False

    worker = get_worker_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": settings.app_name,
        "database": {"connected": db_ok, "dialect": db_dialect},
        "worker": worker,
        "embedding_model": settings.embedding_model_name,
    }
