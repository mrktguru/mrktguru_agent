"""Backlog schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class BacklogTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: str = "medium"
    effort: str | None = None
    phase: str | None = None
    source: str | None = "user"


class BacklogTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    effort: str | None = None
    status: str | None = None
    phase: str | None = None
    position: int | None = None


class BacklogTaskPublic(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None = None
    priority: str
    effort: str | None = None
    status: str
    source: str | None = None
    phase: str | None = None
    position: int
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
