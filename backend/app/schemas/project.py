"""Project and agent message schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    server_id: str | None = None


class ProjectPublic(BaseModel):
    id: str
    name: str
    type: list[str] | None = None
    status: str
    current_phase: int
    spec: dict[str, Any] | None = None
    deploy_path: str | None = None
    domain: str | None = None
    admin_url: str | None = None
    uptime_percent: float | None = None
    deployed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AgentTurnRequest(BaseModel):
    message: str


class AgentTurnResponse(BaseModel):
    reply: str
    phase: int
    phase_complete: bool = False
    spec: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
