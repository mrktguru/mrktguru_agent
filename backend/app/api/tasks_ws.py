"""WebSocket endpoint for streaming task execution logs."""
from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.task import Task
from app.models.task_log import TaskLog

ws_router = APIRouter()


@ws_router.websocket("/ws/tasks/{task_id}")
async def task_logs_ws(websocket, task_id: str, token: str | None = None) -> None:
    """Stream task execution logs. Auth via ?token=JWT."""
    from fastapi.websockets import WebSocketDisconnect

    payload = decode_token(token) if token else None
    if not payload or "sub" not in payload:
        await websocket.close(code=4401)
        return
    user_id = payload["sub"]

    await websocket.accept()
    last_seen_at: datetime | None = None

    try:
        # Send existing logs + verify ownership
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if not task or str(task.user_id) != user_id:
                await websocket.send_json({"type": "error", "message": "not_found"})
                await websocket.close()
                return

            rows = (await db.scalars(
                select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at)
            )).all()
            for row in rows:
                await websocket.send_json(_serialize(row))
                last_seen_at = row.created_at

            terminal_status = task.status

        # Poll until task reaches terminal state
        while terminal_status not in {"done", "failed", "rolled_back"}:
            await asyncio.sleep(0.5)
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(TaskLog)
                    .where(TaskLog.task_id == task.id)
                    .order_by(TaskLog.created_at)
                )
                if last_seen_at is not None:
                    stmt = stmt.where(TaskLog.created_at > last_seen_at)
                new_rows = (await db.scalars(stmt)).all()
                for row in new_rows:
                    await websocket.send_json(_serialize(row))
                    last_seen_at = row.created_at

                task = await db.get(Task, task_id)
                terminal_status = task.status if task else "failed"

        await websocket.send_json({"type": "task_complete", "status": terminal_status})

    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


def _serialize(row: TaskLog) -> dict:
    return {
        "type": "log",
        "id": str(row.id),
        "subtask_index": row.subtask_index,
        "step": row.step,
        "status": row.status,
        "message": row.message,
        "timestamp": row.created_at.isoformat() if row.created_at else None,
    }
