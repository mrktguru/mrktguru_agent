"""Backlog task model."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class BacklogTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "backlog_tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    priority: Mapped[str] = mapped_column(String, default="medium", nullable=False)
    effort: Mapped[str | None] = mapped_column(String, nullable=True)
    # backlog|in_progress|done
    status: Mapped[str] = mapped_column(String, default="backlog", nullable=False)
    # user|agent_suggestion|phase_2|ml_pattern
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    # mvp|post_mvp|future
    phase: Mapped[str | None] = mapped_column(String, nullable=True)

    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
