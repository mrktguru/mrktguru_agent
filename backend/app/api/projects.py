"""Projects API."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DB
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
