"""Projects API."""
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import CurrentUser, DB
from app.core.plans import get_limits, within
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectPublic

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _serialize(p: Project) -> ProjectPublic:
    return ProjectPublic.model_validate(
        {
            "id": str(p.id),
            "name": p.name,
            "type": p.type,
            "status": p.status,
            "current_phase": p.current_phase,
            "spec": p.spec,
            "deploy_path": p.deploy_path,
            "domain": p.domain,
            "admin_url": p.admin_url,
            "uptime_percent": p.uptime_percent,
            "deployed_at": p.deployed_at,
            "created_at": p.created_at,
        }
    )


@router.get("", response_model=list[ProjectPublic])
async def list_projects(user: CurrentUser, db: DB) -> list[ProjectPublic]:
    rows = (await db.scalars(select(Project).where(Project.user_id == user.id))).all()
    return [_serialize(p) for p in rows]


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, user: CurrentUser, db: DB) -> ProjectPublic:
    limits = get_limits(user.plan)
    current = await db.scalar(
        select(func.count(Project.id)).where(Project.user_id == user.id)
    )
    if not within(limits["max_projects"], current or 0):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Достигнут лимит проектов для тарифа '{user.plan}' ({limits['max_projects']})",
        )
    project = Project(
        user_id=user.id,
        name=payload.name,
        server_id=payload.server_id,
        status="draft",
        current_phase=1,
        conversation_history=[],
        spec={},
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _serialize(project)


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(project_id: str, user: CurrentUser, db: DB) -> ProjectPublic:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return _serialize(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, user: CurrentUser, db: DB) -> None:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.patch("/{project_id}/spec", response_model=ProjectPublic)
async def patch_spec(
    project_id: str,
    user: CurrentUser,
    db: DB,
    patch: dict[str, Any] = Body(...),
) -> ProjectPublic:
    """Shallow-merge user-side spec edits (e.g. drag-n-drop in FeatureBoard).

    The patch is shallow-merged into project.spec at top level — frontend
    sends the section it owns (`product`, `workflow`, …).
    """
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    spec: dict[str, Any] = dict(project.spec or {})
    for key, value in (patch or {}).items():
        spec[key] = value
    project.spec = spec
    flag_modified(project, "spec")
    await db.commit()
    await db.refresh(project)
    return _serialize(project)
