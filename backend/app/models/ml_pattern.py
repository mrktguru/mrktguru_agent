"""ML knowledge base patterns (with pgvector embeddings)."""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import UUIDMixin


class MLPattern(UUIDMixin, Base):
    __tablename__ = "ml_patterns"

    project_type: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    feature: Mapped[str] = mapped_column(String, nullable=False)

    frequency: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    usually_requested: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    usually_added_later: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # OpenAI-compatible embedding size; switch to a model that fits if you change provider.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    pattern_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
