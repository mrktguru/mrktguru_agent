"""Tasks API — standalone task endpoints (not nested under sites)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DB
from app.models.task import Task
from app.schemas.site import TaskEstimateResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskEstimateResponse)
async def get_task(task_id: str, user: CurrentUser, db: DB) -> TaskEstimateResponse:
    """Return estimated task by id (used by workspace to load pending quiz TZ)."""
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskEstimateResponse(
        task_id=str(task.id),
        subtasks=task.subtasks or [],
        total_credits=task.estimated_credits or 0,
        confidence=task.confidence or "medium",
        estimated_minutes=10,
    )
