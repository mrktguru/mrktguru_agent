"""Celery application."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "mrktguru_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.execute", "app.tasks.backups"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.on_after_finalize.connect
def _cleanup_on_start(sender, **kwargs):
    from app.tasks.cleanup import cleanup_orphan_tasks
    try:
        cleanup_orphan_tasks()
    except Exception:
        pass
