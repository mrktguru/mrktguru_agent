"""Agent chat API (4-phase product discovery)."""
from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DB
from app.models.project import Project
from app.schemas.project import AgentTurnRequest, AgentTurnResponse
from app.services.agent.service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/{project_id}/chat", response_model=AgentTurnResponse)
async def chat(
    project_id: str,
    payload: AgentTurnRequest,
    user: CurrentUser,
    db: DB,
) -> AgentTurnResponse:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    service = AgentService(db=db)
    result = await service.turn(project, payload.message)
    return AgentTurnResponse(
        reply=result["reply"],
        phase=result["phase"],
        phase_complete=result["phase_complete"],
        spec=result["spec"],
        usage=result["usage"],
    )


@router.get("/{project_id}/history")
async def history(project_id: str, user: CurrentUser, db: DB) -> dict:
    project = await db.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "phase": project.current_phase,
        "spec": project.spec,
        "messages": project.conversation_history or [],
    }
