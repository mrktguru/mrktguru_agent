"""Sites API — manage user's websites and submit tasks."""
from __future__ import annotations

import json
import uuid

from typing import Union

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DB
from app.core.plans import get_limits, within
from app.core.security import decrypt_credentials, encrypt_credentials
from app.models.server import Server
from app.models.site import Site
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.site import (
    ClarificationResponse, ClarifyRequest,
    RejectResponse, ResumeRequest,
    SiteCreate, SitePublic, SiteScanResult,
    TaskCreate, TaskEstimateResponse, TaskPublic, TaskLogPublic,
)
from app.services.ssh.client import SSHClient
from app.services.ssh.scanner import SiteScanner

router = APIRouter(prefix="/api/sites", tags=["sites"])


# ─── helpers ─────────────────────────────────────────────────────────────────

def _serialize_site(s: Site, server_ip: str | None = None) -> SitePublic:
    return SitePublic.model_validate({
        "id": str(s.id),
        "name": s.name,
        "url": s.url,
        "ssh_host": s.ssh_host,
        "server_ip": server_ip or s.ssh_host,
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
        "framework": s.framework,
        "is_docker": bool(s.is_docker),
        "docker_compose_dir": s.docker_compose_dir,
        "docker_service_name": s.docker_service_name,
        "docker_container_name": s.docker_container_name,
        "needs_rebuild": bool(s.needs_rebuild),
        "file_structure": s.file_structure,
        "installed_plugins": s.installed_plugins,
        "audit_score": s.audit_score,
        "uptime_percent": s.uptime_percent,
        "created_at": s.created_at,
    })


async def _build_ssh(site: Site, db: DB) -> SSHClient:
    """Build an SSH client for a site, inheriting creds from its server if needed."""
    enc = site.encrypted_credentials
    host, port, user = site.ssh_host, site.ssh_port, site.ssh_user
    if not enc and site.server_id:
        server = await db.get(Server, site.server_id)
        if server:
            enc = server.encrypted_credentials
            host = host or server.ip
            port = port or server.ssh_port
            user = user or server.ssh_user
    creds = json.loads(decrypt_credentials(enc)) if enc else {}
    return SSHClient(
        host=host,
        username=user,
        port=port,
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

    # Path A: site discovered on a registered server → inherit SSH + creds.
    if payload.server_id is not None:
        server = await db.get(Server, payload.server_id)
        if not server or server.user_id != user.id:
            raise HTTPException(status_code=404, detail="Server not found")
        site = Site(
            user_id=user.id,
            server_id=server.id,
            name=payload.name,
            url=payload.url,
            ssh_host=payload.ssh_host or server.ip,
            ssh_port=payload.ssh_port or server.ssh_port,
            ssh_user=payload.ssh_user or server.ssh_user,
            auth_type=payload.auth_type or server.auth_type,
            encrypted_credentials=None,  # inherited from server at runtime
            cms=payload.cms,
            framework=payload.framework,
            site_root_path=payload.site_root_path,
            is_docker=payload.is_docker,
            docker_compose_dir=payload.docker_compose_dir,
            docker_container_name=payload.docker_container_name,
        )
        db.add(site)
        await db.commit()
        await db.refresh(site)
        return _serialize_site(site)

    # Path B: standalone site with its own credentials.
    if not payload.ssh_host or not payload.auth_type:
        raise HTTPException(status_code=400, detail="ssh_host and auth_type are required without server_id")
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
    server_ip = site.ssh_host
    if not server_ip and site.server_id:
        server = await db.get(Server, site.server_id)
        if server:
            server_ip = server.ip
    return _serialize_site(site, server_ip=server_ip)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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

    # Pass already-known hints so the scanner doesn't re-detect the wrong project
    # on a multi-project server (the user already picked the right one during discovery).
    hints = {
        "docker_compose_dir": site.docker_compose_dir,
        "site_root_path": site.site_root_path,
        "is_docker": site.is_docker,
        "framework": site.framework,
    }

    try:
        ssh_client = await _build_ssh(site, db)
        with ssh_client as ssh:
            scanner = SiteScanner(ssh)
            info = scanner.scan(hints=hints)
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
    # Docker fields — prefer hints if scan couldn't determine them
    site.is_docker = info.get("is_docker", False)
    site.docker_compose_dir = info.get("docker_compose_dir") or site.docker_compose_dir
    site.docker_service_name = info.get("docker_service_name")
    site.docker_container_name = info.get("docker_container_name")
    site.framework = info.get("framework") or site.framework
    site.needs_rebuild = info.get("needs_rebuild", False)
    site.status = "active"
    await db.commit()

    return SiteScanResult(**{k: v for k, v in info.items() if k in SiteScanResult.model_fields})


# ─── Tasks ───────────────────────────────────────────────────────────────────

@router.get("/{site_id}/tasks", response_model=list[TaskPublic])
async def list_tasks(site_id: str, user: CurrentUser, db: DB) -> list[TaskPublic]:
    await _get_site_or_404(site_id, user.id, db)
    rows = (await db.scalars(
        select(Task).where(Task.site_id == uuid.UUID(site_id)).order_by(Task.created_at.desc())
    )).all()
    return [TaskPublic.from_task(t) for t in rows]


@router.post("/{site_id}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(site_id: str, payload: TaskCreate, user: CurrentUser, db: DB) -> Union[TaskEstimateResponse, ClarificationResponse, RejectResponse]:
    """Submit a TZ → agent estimates subtasks OR asks clarifying questions."""
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

    # ── Stage 0: two-level triage (cheap haiku call) ─────────────────────────
    from app.services.agent.triage import triage as run_triage
    tri = run_triage(site, payload.tz_text)
    task.intent = tri.get("intent")
    task.task_type = tri.get("type")
    task.triage = tri  # decision log
    # Hard reject — out of scope / malicious. No estimation, no edits.
    if tri.get("intent") == "reject":
        rej = tri.get("reject") or {}
        task.status = "rejected"
        task.error_message = rej.get("message") or "Запрос вне возможностей сервиса."
        await db.commit()
        return RejectResponse(
            task_id=str(task.id),
            reason=rej.get("reason", "out_of_scope"),
            message=task.error_message,
        )

    # Try to build a live SSH connection so the estimator can read real files.
    # If SSH is unavailable we fall back gracefully to DB-stored file_structure.
    ssh_client = None
    try:
        ssh_client = await _build_ssh(site, db)
        ssh_client.connect()
    except Exception:
        ssh_client = None  # silently degrade — estimation still works via DB

    # Fetch recent completed tasks so the estimator can understand follow-up messages
    # (e.g. "the changes didn't apply" → agent sees what files were changed last time)
    from sqlalchemy import select as sa_select
    prev_tasks = list(reversed((await db.scalars(
        sa_select(Task)
        .where(Task.site_id == uuid.UUID(site_id), Task.id != task.id,
               Task.status.in_(["done", "failed", "rolled_back"]))
        .order_by(Task.created_at.desc())
        .limit(5)
    )).all()))

    # Run estimation
    try:
        estimator = TaskEstimator(site, task, ssh=ssh_client, previous_tasks=prev_tasks)
        estimate = await estimator.estimate()
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Estimation failed: {exc}") from exc
    finally:
        if ssh_client:
            try:
                ssh_client.close()
            except Exception:
                pass

    # Agent needs clarification before it can plan work
    if estimate.get("status") == "needs_clarification":
        questions = estimate.get("questions", [])
        task.status = "clarifying"
        task.error_message = "\n".join(questions)
        # Start clarify_qa history with the first set of questions
        task.clarify_qa = [{"questions": questions, "answer": None}]
        await db.commit()
        return ClarificationResponse(
            task_id=str(task.id),
            status="needs_clarification",
            summary=estimate.get("summary", ""),
            questions=questions,
        )

    task.title = estimate.get("title", payload.tz_text[:80])
    task.subtasks = estimate.get("subtasks", [])
    task.tracks = estimate.get("tracks")  # typed tracks (None if estimator didn't emit)
    task.estimated_credits = estimate.get("total_credits", 0)
    task.estimated_minutes = estimate.get("estimated_minutes", 10)
    task.confidence = estimate.get("confidence", "medium")
    task.status = "estimated"
    await db.commit()

    return TaskEstimateResponse(
        task_id=str(task.id),
        subtasks=estimate.get("subtasks", []),
        total_credits=estimate.get("total_credits", 0),
        confidence=estimate.get("confidence", "medium"),
        estimated_minutes=estimate.get("estimated_minutes", 10),
        tracks=estimate.get("tracks"),
        intent=task.intent,
        type=task.task_type,
    )


@router.post("/{site_id}/tasks/{task_id}/clarify", status_code=status.HTTP_200_OK)
async def clarify_task(
    site_id: str,
    task_id: str,
    payload: ClarifyRequest,
    user: CurrentUser,
    db: DB,
) -> Union[TaskEstimateResponse, ClarificationResponse]:
    """User provides answers to clarifying questions → re-estimate."""
    from app.services.agent.task_estimator import TaskEstimator

    site = await _get_site_or_404(site_id, user.id, db)
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "clarifying":
        raise HTTPException(status_code=400, detail="Task is not awaiting clarification")

    try:
        estimator = TaskEstimator(site, task)
        estimate = await estimator.clarify(payload.answers)
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Clarification failed: {exc}") from exc

    # Save user's answer into the last Q&A turn
    qa = list(task.clarify_qa or [])
    if qa and qa[-1].get("answer") is None:
        qa[-1]["answer"] = payload.answers
    else:
        qa.append({"questions": [], "answer": payload.answers})

    # Still needs more clarification
    if estimate.get("status") == "needs_clarification":
        new_questions = estimate.get("questions", [])
        qa.append({"questions": new_questions, "answer": None})
        task.clarify_qa = qa
        task.error_message = "\n".join(new_questions)
        await db.commit()
        return ClarificationResponse(
            task_id=str(task.id),
            status="needs_clarification",
            summary=estimate.get("summary", ""),
            questions=new_questions,
        )

    task.title = estimate.get("title", task.tz_text[:80] if task.tz_text else "Задача")
    task.subtasks = estimate.get("subtasks", [])
    task.estimated_credits = estimate.get("total_credits", 0)
    task.estimated_minutes = estimate.get("estimated_minutes", 10)
    task.confidence = estimate.get("confidence", "medium")
    task.error_message = None
    task.clarify_qa = qa
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

    return TaskPublic.from_task(task)


@router.get("/{site_id}/tasks/{task_id}/logs", response_model=list[TaskLogPublic])
async def get_task_logs(site_id: str, task_id: str, user: CurrentUser, db: DB) -> list[TaskLogPublic]:
    await _get_site_or_404(site_id, user.id, db)
    rows = (await db.scalars(
        select(TaskLog).where(TaskLog.task_id == uuid.UUID(task_id)).order_by(TaskLog.created_at)
    )).all()
    return [TaskLogPublic.model_validate(r.__dict__) for r in rows]


@router.post("/{site_id}/tasks/{task_id}/rollback", response_model=TaskPublic)
async def rollback_task(site_id: str, task_id: str, user: CurrentUser, db: DB) -> TaskPublic:
    """Rollback all changes made by a task (restore files + rebuild + verify).

    Runs asynchronously in a Celery worker; progress streams over the task
    WebSocket. The client should reconnect to /ws/tasks/{task_id} to watch it.
    """
    from app.tasks.execute import run_rollback

    await _get_site_or_404(site_id, user.id, db)
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(status_code=400, detail=f"Откат доступен только для завершённых задач (статус: {task.status})")
    if not task.backup_available:
        raise HTTPException(status_code=400, detail="Бэкап недоступен — откат невозможен")

    # Reflect the in-progress state immediately; the worker sets the final status.
    task.status = "rolling_back"
    await db.commit()

    run_rollback.delay(str(task.id))

    return TaskPublic.from_task(task)
