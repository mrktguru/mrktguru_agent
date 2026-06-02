"""Tasks API — standalone task endpoints (not nested under sites)."""
from __future__ import annotations

from typing import Union

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DB
from app.models.task import Task
from app.schemas.site import ClarificationResponse, TaskEstimateResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=Union[TaskEstimateResponse, ClarificationResponse])
async def get_task(task_id: str, user: CurrentUser, db: DB) -> Union[TaskEstimateResponse, ClarificationResponse]:
    """Return task state (used by workspace to load pending TZ).

    Returns ClarificationResponse when the task is still awaiting clarification
    so the workspace can render the Q&A UI instead of an empty subtask list.
    """
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "clarifying":
        questions: list[str] = []
        if task.clarify_qa:
            last = task.clarify_qa[-1]
            questions = last.get("questions") or []
        if not questions and task.error_message:
            questions = [q for q in task.error_message.splitlines() if q.strip()]
        return ClarificationResponse(
            task_id=str(task.id),
            status="needs_clarification",
            summary=task.tz_text or "",
            questions=questions,
        )

    return TaskEstimateResponse(
        task_id=str(task.id),
        subtasks=task.subtasks or [],
        total_credits=task.estimated_credits or 0,
        confidence=task.confidence or "medium",
        estimated_minutes=10,
    )
