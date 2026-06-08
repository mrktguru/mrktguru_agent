"""Celery task: index a completed task as a reusable solution."""
from __future__ import annotations

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="solutions.index", bind=True, max_retries=0)
def index_solution_task(self, task_id: str) -> dict:
    """Fire-and-forget: index task as reusable solution if it passes quality filter."""
    try:
        from app.services.solutions.indexer import index_solution
        index_solution(task_id)
        return {"task_id": task_id, "status": "indexed"}
    except Exception as exc:
        logger.warning("index_solution_task failed for %s: %s", task_id, exc)
        return {"task_id": task_id, "status": "error", "error": str(exc)}
