"""Monitoring tasks (uptime, resource usage)."""
from app.tasks.celery_app import celery_app


@celery_app.task(name="monitor.heartbeat")
def heartbeat(project_id: str) -> dict:
    return {"project_id": project_id, "status": "alive"}
