"""Project model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    # ['telegram_bot', 'web_app', 'parser', 'landing']
    type: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # draft|building|deployed|error
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    current_phase: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Full project specification (see COPILOT.md "JSON спецификация проекта")
    spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # List of {role, content} dicts
    conversation_history: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    deploy_path: Mapped[str | None] = mapped_column(String, nullable=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    admin_url: Mapped[str | None] = mapped_column(String, nullable=True)

    uptime_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
