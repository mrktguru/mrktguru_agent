"""WebSocket endpoint for streaming task execution logs."""
from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.task import Task
from app.models.task_log import TaskLog

ws_router = APIRouter()

TERMINAL = {"done", "failed", "rolled_back", "answered", "rejected", "stalled"}
# Non-terminal stop: task suspended waiting for the user to provide input.
PAUSED = "waiting_for_user"
# Per-step billing-meter rows are hidden from the human log stream.
META_STEP = "meter"


def _stop_event(task) -> dict:
    """Build the WS event that ends a streaming session for a stopped task."""
    if task.status == PAUSED:
        return {
            "type": "task_paused",
            "status": PAUSED,
            "pending_input": task.pending_input or {},
        }
    ev = {"type": "task_complete", "status": task.status}
    if task.status == "answered":
        ev["answer"] = task.answer_text
    if task.agent_summary:
        ev["agent_summary"] = task.agent_summary
    return ev


@ws_router.websocket("/ws/tasks/{task_id}")
async def task_logs_ws(websocket: WebSocket, task_id: str, token: str | None = None) -> None:
    """Stream task execution logs. Auth via ?token=JWT."""
    payload = decode_token(token) if token else None
    if not payload or "sub" not in payload:
        await websocket.close(code=4401)
        return
    user_id = payload["sub"]

    await websocket.accept()
    last_seen_at: datetime | None = None

    try:
        # ── 1. Verify ownership & send all existing logs immediately ─────────
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if not task or str(task.user_id) != user_id:
                await websocket.send_json({"type": "error", "message": "not_found"})
                await websocket.close()
                return

            rows = (await db.scalars(
                select(TaskLog)
                .where(TaskLog.task_id == task.id)
                .where(TaskLog.step.is_distinct_from(META_STEP))
                .order_by(TaskLog.created_at)
            )).all()
            for row in rows:
                await websocket.send_json(_serialize(row))
                last_seen_at = row.created_at

            stop_task = task if (task.status in TERMINAL or task.status == PAUSED) else None

        # If task already stopped before WS connected → send the stop event immediately
        if stop_task is not None:
            await websocket.send_json(_stop_event(stop_task))
            return

        # ── 2. Poll for new logs until terminal state ─────────────────────────
        while True:
            await asyncio.sleep(0.4)
            async with AsyncSessionLocal() as db:
                # New logs
                stmt = (
                    select(TaskLog)
                    .where(TaskLog.task_id == task.id)
                    .where(TaskLog.step.is_distinct_from(META_STEP))
                    .order_by(TaskLog.created_at)
                )
                if last_seen_at is not None:
                    stmt = stmt.where(TaskLog.created_at > last_seen_at)
                new_rows = (await db.scalars(stmt)).all()
                for row in new_rows:
                    await websocket.send_json(_serialize(row))
                    last_seen_at = row.created_at

                # Check task status
                refreshed = await db.get(Task, task_id)
                status_now = refreshed.status if refreshed else "failed"
                stop_task = refreshed if (status_now in TERMINAL or status_now == PAUSED) else None

            if stop_task is not None:
                await websocket.send_json(_stop_event(stop_task))
                break

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
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
