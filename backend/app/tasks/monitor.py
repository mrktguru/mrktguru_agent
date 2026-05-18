"""Monitoring tasks (uptime, resource usage).

`monitor_all` is scheduled by Celery beat every 5 minutes and pings every
deployed project. Results update `projects.uptime_percent` using a simple
EMA (alpha=0.1) and emit a `DeployLog` row when state changes.
"""
from __future__ import annotations

import socket
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from celery.schedules import crontab
from sqlalchemy import select

from app.core.database import SyncSessionLocal
from app.models.deploy_log import DeployLog
from app.models.project import Project
from app.tasks.celery_app import celery_app


def _ping(url: str, timeout: float = 8.0) -> bool:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={"User-Agent": "appforge-monitor/1.0"})
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return 200 <= resp.status < 500
    except (socket.timeout, OSError, ValueError):
        return False


def _ema(prev: float | None, sample: float, alpha: float = 0.1) -> float:
    if prev is None:
        return sample
    return round(prev * (1 - alpha) + sample * alpha, 4)


@celery_app.task(name="monitor.heartbeat")
def heartbeat(project_id: str) -> dict:
    with SyncSessionLocal() as db:
        project = db.get(Project, project_id)
        if not project or project.status != "deployed":
            return {"project_id": project_id, "status": "skipped"}

        url = (
            f"https://{project.domain}/" if project.domain
            else None
        )
        if not url:
            return {"project_id": project_id, "status": "no_domain"}

        alive = _ping(url)
        previous_alive = (project.uptime_percent or 0) > 0.5
        project.uptime_percent = _ema(project.uptime_percent, 1.0 if alive else 0.0)

        if alive != previous_alive:
            db.add(
                DeployLog(
                    project_id=project.id,
                    step="monitor",
                    status="success" if alive else "error",
                    message=("проект ожил" if alive else "проект недоступен"),
                )
            )
        db.commit()
        return {"project_id": project_id, "alive": alive, "uptime": project.uptime_percent}


@celery_app.task(name="monitor.run_all")
def monitor_all() -> dict:
    checked = 0
    with SyncSessionLocal() as db:
        ids = db.scalars(select(Project.id).where(Project.status == "deployed")).all()
    for pid in ids:
        heartbeat.delay(str(pid))
        checked += 1
    return {"queued": checked}


# Celery beat: run monitor_all every 5 minutes.
celery_app.conf.beat_schedule = {
    "monitor-every-5-min": {
        "task": "monitor.run_all",
        "schedule": crontab(minute="*/5"),
    },
}
