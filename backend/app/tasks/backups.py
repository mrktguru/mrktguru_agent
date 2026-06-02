"""Backup retention — daily prune of file backups older than the retention window.

Backups live on each *target site server* under settings.SITEDOC_BACKUP_DIR, one
sub-directory per task id. This Celery-beat task SSHes into every site that still
has rollback-able tasks, deletes archives older than the retention window, and
clears `Task.backup_available` for tasks whose backups are gone.
"""
from __future__ import annotations

import shlex

from celery.schedules import crontab
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.site import Site
from app.models.task import Task
from app.tasks.celery_app import celery_app
from app.tasks.execute import _build_ssh_for_site


@celery_app.task(name="backups.cleanup")
def cleanup_old_backups() -> dict:
    days = settings.SITEDOC_BACKUP_RETENTION_DAYS
    base = settings.SITEDOC_BACKUP_DIR
    processed = 0

    with SyncSessionLocal() as db:
        site_ids = db.scalars(
            select(Task.site_id).where(Task.backup_available.is_(True)).distinct()
        ).all()

        for sid in site_ids:
            site = db.get(Site, sid)
            if not site:
                continue

            remaining: set[str] = set()
            ssh = _build_ssh_for_site(db, site)
            try:
                ssh.connect()
                # Delete archives older than the retention window, then prune empty dirs.
                ssh.run(
                    f"find {shlex.quote(base)} -name 'subtask_*.tar.gz' -mtime +{days} -delete",
                    timeout=60,
                )
                ssh.run(f"find {shlex.quote(base)} -mindepth 1 -type d -empty -delete", timeout=60)
                _, out, _ = ssh.run(f"ls {shlex.quote(base)} 2>/dev/null || echo ''", timeout=30)
                remaining = {line.strip() for line in out.splitlines() if line.strip()}
            except Exception:
                continue  # skip unreachable sites this cycle
            finally:
                try:
                    ssh.close()
                except Exception:
                    pass

            tasks = db.scalars(
                select(Task).where(Task.site_id == sid, Task.backup_available.is_(True))
            ).all()
            for t in tasks:
                if str(t.id) not in remaining:
                    t.backup_available = False
            db.commit()
            processed += 1

    return {"sites_processed": processed}


# Register the daily cleanup alongside any existing beat schedule (e.g. monitor).
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "cleanup-backups-daily": {
        "task": "backups.cleanup",
        "schedule": crontab(hour="3", minute="0"),
    },
}
