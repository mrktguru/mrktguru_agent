"""Stack presets per project type."""
from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import UUIDMixin


class StackPreset(UUIDMixin, Base):
    __tablename__ = "stack_presets"

    project_type: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    stack: Mapped[dict] = mapped_column(JSONB, nullable=False)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    common_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
