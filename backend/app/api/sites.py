"""Sites API — manage user's websites and submit tasks."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DB
from app.core.plans import get_limits, within
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.site import (
    SiteCreate, SitePublic, SiteScanResult,
    TaskCreate, TaskEstimateResponse, TaskPublic, TaskLogPublic,
)
from app.services.ssh.client import SSHClient
from app.services.ssh.scanner import SiteScanner

router = APIRouter(prefix="/api/sites", tags=["sites"])


# ─── helpers ─────────────────────────────────────────────────────────────────

def _serialize_site(s: Site) -> SitePublic:
    return SitePublic.model_validate({
        "id": str(s.id),
        "name": s.name,
        "url": s.url,
        "ssh_host": s.ssh_host,
        "ssh_port": s.ssh_port,
        "ssh_user": s.ssh_user,
        "auth_type": s.auth_type,
        "status": s.status,
        "cms": s.cms,
        "cms_version": s.cms_version,
        "php_version": s.php_version,
        "web_server": s.web_server,
        "server_os": s.server_os,
        "site_root_path": s.site_root_path,
        "audit_score": s.audit_score,
        "uptime_percent": s.uptime_percent,
        "created_at": s.created_at,
    })


def _build_ssh(site: Site) -> SSHClient:
    creds = json.loads(decrypt_credentials(site.encrypted_credentials)) if site.encrypted_credentials else {}
    return SSHClient(
        host=site.ssh_host,
        username=site.ssh_user,
        port=site.ssh_port,
        password=creds.get("password"),
        private_key=creds.get("private_key"),
    )


async def _get_site_or_404(site_id: str, user_id: uuid.UUID, db: DB) -> Site:
    site = await db.get(Site, site_id)
    if not site or site.user_id != user_id:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ─── Sites CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[SitePublic])
async def list_sites(user: CurrentUser, db: DB) -> list[SitePublic]:
    rows = (await db.scalars(select(Site).where(Site.user_id == user.id))).all()
    return [_serialize_site(s) for s in rows]


@router.post("", response_model=SitePublic, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreate, user: CurrentUser, db: DB) -> SitePublic:
    limits = get_limits(user.plan)
    current = await db.scalar(select(func.count(Site.id)).where(Site.user_id == user.id))
    if not within(limits["max_sites"], current or 0):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Достигнут лимит сайтов для тарифа '{user.plan}' ({limits['max_sites']})",
        )

    creds: dict[str, str] = {}
    if payload.auth_type == "password":
        if not payload.password:
            raise HTTPException(status_code=400, detail="password is required for auth_type=password")
        creds["password"] = payload.password
    elif payload.private_key:
        creds["private_key"] = payload.private_key

    site = Site(
        user_id=user.id,
        name=payload.name,
        url=payload.url,
        ssh_host=payload.ssh_host,
        ssh_port=payload.ssh_port,
        ssh_user=payload.ssh_user,
        auth_type=payload.auth_type,
        encrypted_credentials=encrypt_credentials(json.dumps(creds)) if creds else None,
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return _serialize_site(site)


@router.get("/{site_id}", response_model=SitePublic)
async def get_site(site_id: str, user: CurrentUser, db: DB) -> SitePublic:
    site = await _get_site_or_404(site_id, user.id, db)
    return _serialize_site(site)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: str, user: CurrentUser, db: DB) -> None:
    site = await _get_site_or_404(site_id, user.id, db)
    await db.delete(site)
    await db.commit()


# ─── Site scan ───────────────────────────────────────────────────────────────

@router.post("/{site_id}/scan", response_model=SiteScanResult)
async def scan_site(site_id: str, user: CurrentUser, db: DB) -> SiteScanResult:
    site = await _get_site_or_404(site_id, user.id, db)
    site.status = "scanning"
    await db.commit()

    try:
        with _build_ssh(site) as ssh:
            scanner = SiteScanner(ssh)
            info = scanner.scan()
    except Exception as exc:
        site.status = "error"
        await db.commit()
        raise HTTPException(status_code=400, detail=f"SSH scan failed: {exc}") from exc

    site.cms = info.get("cms")
    site.cms_version = info.get("cms_version")
    site.php_version = info.get("php_version")
    site.web_server = info.get("web_server")
    site.server_os = info.get("server_os")
    site.site_root_path = info.get("site_root_path")
    site.file_structure = info.get("file_structure")
    site.installed_plugins = info.get("installed_plugins")
    site.status = "active"
    await db.commit()

    return SiteScanResult(**info)


# ─── Tasks ───────────────────────────────────────────────────────────────────

@router.get("/{site_id}/tasks", response_model=list[TaskPublic])
async def list_tasks(site_id: str, user: CurrentUser, db: DB) -> list[TaskPublic]:
    await _get_site_or_404(site_id, user.id, db)
    rows = (await db.scalars(
        select(Task).where(Task.site_id == uuid.UUID(site_id)).order_by(Task.created_at.desc())
    )).all()
    return [TaskPublic.model_validate(t.__dict__) for t in rows]


@router.post("/{site_id}/tasks", response_model=TaskEstimateResponse, status_code=status.HTTP_201_CREATED)
async def create_task(site_id: str, payload: TaskCreate, user: CurrentUser, db: DB) -> TaskEstimateResponse:
    """Submit a TZ → agent estimates subtasks and returns them for user approval."""
    from app.services.agent.task_estimator import TaskEstimator

    site = await _get_site_or_404(site_id, user.id, db)

    # Create task in pending state
    task = Task(
        site_id=uuid.UUID(site_id),
        user_id=user.id,
        tz_text=payload.tz_text,
        reference_urls=payload.reference_urls,
        attachments=payload.attachments,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Run estimation
    try:
        estimator = TaskEstimator(site, task)
        estimate = await estimator.estimate()
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Estimation failed: {exc}") from exc

    task.title = estimate.get("title", payload.tz_text[:80])
    task.subtasks = estimate.get("subtasks", [])
    task.estimated_credits = estimate.get("total_credits", 0)
    task.confidence = estimate.get("confidence", "medium")
    task.status = "estimated"
    await db.commit()

    return TaskEstimateResponse(
        task_id=str(task.id),
        subtasks=estimate.get("subtasks", []),
        total_credits=estimate.get("total_credits", 0),
        confidence=estimate.get("confidence", "medium"),
        estimated_minutes=estimate.get("estimated_minutes", 10),
    )


@router.post("/{site_id}/tasks/{task_id}/approve", response_model=TaskPublic)
async def approve_task(
    site_id: str,
    task_id: str,
    user: CurrentUser,
    db: DB,
    enabled_subtask_ids: list[str] | None = None,
) -> TaskPublic:
    """User confirms execution. Enqueues Celery task."""
    from app.tasks.execute import run_execute

    site = await _get_site_or_404(site_id, user.id, db)
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "estimated":
        raise HTTPException(status_code=400, detail=f"Task status is '{task.status}', expected 'estimated'")

    # Filter subtasks if user deselected some
    if enabled_subtask_ids is not None and task.subtasks:
        task.subtasks = [s for s in task.subtasks if s.get("id") in enabled_subtask_ids]
        task.estimated_credits = sum(s.get("estimated_credits", 0) for s in task.subtasks)

    task.status = "approved"
    await db.commit()

    # Enqueue async execution
    run_execute.delay(str(task.id))

    return TaskPublic.model_validate(task.__dict__)


@router.get("/{site_id}/tasks/{task_id}/logs", response_model=list[TaskLogPublic])
async def get_task_logs(site_id: str, task_id: str, user: CurrentUser, db: DB) -> list[TaskLogPublic]:
    await _get_site_or_404(site_id, user.id, db)
    rows = (await db.scalars(
        select(TaskLog).where(TaskLog.task_id == uuid.UUID(task_id)).order_by(TaskLog.created_at)
    )).all()
    return [TaskLogPublic.model_validate(r.__dict__) for r in rows]


@router.post("/{site_id}/tasks/{task_id}/rollback", response_model=TaskPublic)
async def rollback_task(site_id: str, task_id: str, user: CurrentUser, db: DB) -> TaskPublic:
    """Rollback all changes made by a task."""
    from app.services.ssh.backup import BackupManager

    site = await _get_site_or_404(site_id, user.id, db)
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        with _build_ssh(site) as ssh:
            bm = BackupManager(ssh)
            bm.restore_all(str(task.id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {exc}") from exc

    task.status = "rolled_back"
    await db.commit()
    return TaskPublic.model_validate(task.__dict__)
