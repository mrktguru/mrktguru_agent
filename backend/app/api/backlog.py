"""Backlog API."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
from app.models.backlog import BacklogTask
from app.models.project import Project
from app.schemas.backlog import BacklogTaskCreate, BacklogTaskPublic, BacklogTaskUpdate

router = APIRouter(prefix="/api/projects/{project_id}/backlog", tags=["backlog"])


async def _owned_project(project_id: str, user_id, db) -> Project:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _serialize(t: BacklogTask) -> BacklogTaskPublic:
    return BacklogTaskPublic.model_validate(
        {
            "id": str(t.id),
            "project_id": str(t.project_id),
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "effort": t.effort,
            "status": t.status,
            "source": t.source,
            "phase": t.phase,
            "position": t.position,
            "completed_at": t.completed_at,
            "created_at": t.created_at,
        }
    )


@router.get("", response_model=list[BacklogTaskPublic])
async def list_tasks(project_id: str, user: CurrentUser, db: DB) -> list[BacklogTaskPublic]:
    await _owned_project(project_id, user.id, db)
    rows = (
        await db.scalars(
            select(BacklogTask)
            .where(BacklogTask.project_id == project_id)
            .order_by(BacklogTask.position, BacklogTask.created_at)
        )
    ).all()
    return [_serialize(t) for t in rows]


@router.post("", response_model=BacklogTaskPublic, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: str, payload: BacklogTaskCreate, user: CurrentUser, db: DB
) -> BacklogTaskPublic:
    await _owned_project(project_id, user.id, db)
    task = BacklogTask(project_id=project_id, **payload.model_dump(exclude_none=True))
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _serialize(task)


@router.patch("/{task_id}", response_model=BacklogTaskPublic)
async def update_task(
    project_id: str, task_id: str, payload: BacklogTaskUpdate, user: CurrentUser, db: DB
) -> BacklogTaskPublic:
    await _owned_project(project_id, user.id, db)
    task = await db.get(BacklogTask, task_id)
    if not task or str(task.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(task, k, v)
    await db.commit()
    await db.refresh(task)
    return _serialize(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(project_id: str, task_id: str, user: CurrentUser, db: DB) -> None:
    await _owned_project(project_id, user.id, db)
    task = await db.get(BacklogTask, task_id)
    if not task or str(task.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
