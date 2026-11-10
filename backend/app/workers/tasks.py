from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import UUID
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.discovery.pipeline import execute_discovery_pipeline
from app.models.discovery import DiscoveryJob
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_local_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="edxso-worker")
_active_job_locks: set[str] = set()
_lock_guard = Lock()


def _run_job_with_guard(job_id_str: str) -> None:
    with _lock_guard:
        if job_id_str in _active_job_locks:
            return
        _active_job_locks.add(job_id_str)

    db = SessionLocal()
    try:
        execute_discovery_pipeline(db, UUID(job_id_str))
    except Exception as exc:
        logger.error("discovery_job_failed", job_id=job_id_str, error=str(exc))
    finally:
        db.close()
        with _lock_guard:
            _active_job_locks.discard(job_id_str)


@celery_app.task(
    bind=True,
    name="edxso.run_discovery_job",
    max_retries=2,
    default_retry_delay=5,
)
def run_discovery_job_task(self, job_id_str: str) -> dict:
    db = SessionLocal()
    try:
        job = execute_discovery_pipeline(db, UUID(job_id_str))
        return {
            "job_id": str(job.id),
            "status": job.status,
            "total_evaluated": job.total_candidates_evaluated,
        }
    except Exception as exc:
        logger.warning("celery_discovery_retry", job_id=job_id_str, attempt=self.request.retries, error=str(exc))
        if self.request.retries < self.max_retries:
            j = db.query(DiscoveryJob).filter(DiscoveryJob.id == UUID(job_id_str)).first()
            if j:
                j.status = "RETRYING"
                j.retry_count = self.request.retries + 1
                db.commit()
            raise self.retry(exc=exc)
        raise
    finally:
        db.close()


def enqueue_discovery_job(job_id: UUID) -> str:
    """Dispatch discovery job to Celery/Redis when configured, or local worker pool fallback."""
    settings = get_settings()
    job_id_str = str(job_id)

    if settings.task_queue_mode.lower() == "celery":
        try:
            async_res = run_discovery_job_task.delay(job_id_str)
            return str(async_res.id)
        except Exception as exc:
            logger.warning("celery_dispatch_fallback_to_local", error=str(exc))

    _local_executor.submit(_run_job_with_guard, job_id_str)
    return f"local-{job_id_str[:8]}"


def get_worker_health() -> dict:
    settings = get_settings()
    mode = settings.task_queue_mode.lower()
    if mode == "celery":
        try:
            insp = celery_app.control.inspect(timeout=1.0)
            active = insp.ping() if insp else None
            return {
                "mode": "celery",
                "healthy": bool(active),
                "workers": list(active.keys()) if active else [],
            }
        except Exception as exc:
            return {"mode": "celery", "healthy": False, "error": str(exc)}
    return {
        "mode": "local_threadpool",
        "healthy": True,
        "active_jobs": len(_active_job_locks),
    }
