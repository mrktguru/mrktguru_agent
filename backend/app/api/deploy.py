"""Deploy API: trigger pipeline, list logs, stream over WebSocket."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.deps import CurrentUser, DB
from app.core.security import decode_token
from app.models.deploy_log import DeployLog
from app.models.project import Project
from app.tasks.deploy import run_deploy

router = APIRouter(prefix="/api/projects/{project_id}/deploy", tags=["deploy"])


@router.post("")
async def trigger_deploy(project_id: str, user: CurrentUser, db: DB) -> dict[str, Any]:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.server_id:
        raise HTTPException(status_code=400, detail="Project has no server assigned")
    task = run_deploy.delay(str(project.id))
    return {"task_id": task.id, "status": "queued"}


@router.get("/logs")
async def list_logs(project_id: str, user: CurrentUser, db: DB) -> list[dict[str, Any]]:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    rows = (
        await db.scalars(
            select(DeployLog)
            .where(DeployLog.project_id == project_id)
            .order_by(DeployLog.created_at)
        )
    ).all()
    return [_serialize_log(r) for r in rows]


def _serialize_log(row: DeployLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "step": row.step,
        "status": row.status,
        "message": row.message,
        "raw_output": row.raw_output,
        "timestamp": _iso(row.created_at),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# ---- WebSocket --------------------------------------------------------------


ws_router = APIRouter()


@ws_router.websocket("/ws/deploy/{project_id}")
async def deploy_ws(websocket: WebSocket, project_id: str, token: str | None = None) -> None:
    """Stream deploy logs.

    Auth: JWT passed via ?token=... query string (browsers can't set headers on WS).
    """
    payload = decode_token(token) if token else None
    if not payload or "sub" not in payload:
        await websocket.close(code=4401)
        return
    user_id = payload["sub"]

    await websocket.accept()
    last_seen_at: datetime | None = None

    try:
        # 1. Verify project ownership + send everything that already exists.
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, project_id)
            if not project or str(project.user_id) != user_id:
                await websocket.send_json({"type": "error", "message": "not_found"})
                await websocket.close()
                return

            rows = (
                await db.scalars(
                    select(DeployLog)
                    .where(DeployLog.project_id == project_id)
                    .order_by(DeployLog.created_at)
                )
            ).all()
            for row in rows:
                await websocket.send_json({"type": "log", **_serialize_log(row)})
                last_seen_at = row.created_at

            terminal_status = project.status

        # 2. Poll for new logs until project reaches terminal state.
        while terminal_status not in {"deployed", "error"}:
            await asyncio.sleep(0.5)
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(DeployLog)
                    .where(DeployLog.project_id == project_id)
                    .order_by(DeployLog.created_at)
                )
                if last_seen_at is not None:
                    stmt = stmt.where(DeployLog.created_at > last_seen_at)
                new_rows = (await db.scalars(stmt)).all()
                for row in new_rows:
                    await websocket.send_json({"type": "log", **_serialize_log(row)})
                    last_seen_at = row.created_at

                project = await db.get(Project, project_id)
                terminal_status = project.status if project else "error"

        await websocket.send_json({"type": "deploy_complete", "status": terminal_status})
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
