"""Cleanup stuck tasks on worker startup.

Tasks stuck in 'running' or 'approved' state after a worker crash/restart
will never complete — mark them as 'failed' so the UI shows a clear state.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ORPHAN_STATUSES = {"running", "approved", "rolling_back", "waiting_for_user"}
ORPHAN_AFTER_MINUTES = 10


def cleanup_orphan_tasks() -> int:
    """Mark stuck tasks as failed. Returns count of cleaned tasks."""
    from app.core.database import SyncSessionLocal
    from app.models.task import Task
    from app.models.task_log import TaskLog
    from app.services.billing.settlement import settle
    from sqlalchemy import func, select

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ORPHAN_AFTER_MINUTES)
    cleaned = 0

    try:
        with SyncSessionLocal() as db:
            stuck = db.scalars(
                select(Task).where(
                    Task.status.in_(ORPHAN_STATUSES),
                    Task.created_at < cutoff,
                )
            ).all()

            for task in stuck:
                msg = "⚠ Задача прервана при перезапуске системы. Запустите заново."
                db.add(TaskLog(
                    task_id=task.id,
                    step="error", status="error",
                    message=msg,
                ))
                spent = float(db.scalar(
                    select(func.coalesce(func.sum(TaskLog.credits), 0.0))
                    .where(TaskLog.task_id == task.id)
                ) or 0.0)
                if task.settled_at is None:
                    settle(db, task, spent_credits=spent, status="failed")
                # Always force terminal status — settled_at may be set but status stuck.
                task.status = "failed"
                task.error_message = "Прервано при перезапуске системы"
                cleaned += 1

            if cleaned:
                db.commit()
                logger.info("cleanup_orphan_tasks: marked %d stuck tasks as failed", cleaned)
    except Exception as e:
        logger.warning("cleanup_orphan_tasks failed: %s", e)

    return cleaned
