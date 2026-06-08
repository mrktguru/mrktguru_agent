"""Solution reuse models (SOLUTION_REUSE.md §1.3)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector as _Vector
    _VEC = _Vector(1536)
except ImportError:
    _VEC = None  # type: ignore[assignment]


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(20), nullable=False)     # curated_skill | accumulated
    level: Mapped[str] = mapped_column(String(12), nullable=False)      # snippet | template | pattern

    task_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stack: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stack_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    required_deps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    required_env: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    expected_files: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    key_patterns: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    success_rate: Mapped[float] = mapped_column(Float, server_default=text("0.95"), nullable=False)
    reuse_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    avg_steps_saved: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_credits_saved: Mapped[float | None] = mapped_column(Float, nullable=True)
    trusted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_to_skill: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)

    if _VEC is not None:
        from sqlalchemy import Column as _Col
        embedding = _Col(_VEC, nullable=True)


class Pattern(Base):
    __tablename__ = "patterns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stack: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lesson: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, server_default=text("0.5"), nullable=False)
    observed_count: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    if _VEC is not None:
        from sqlalchemy import Column as _Col
        embedding = _Col(_VEC, nullable=True)


class ReuseLog(Base):
    __tablename__ = "reuse_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    solution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solutions.id", ondelete="SET NULL"), nullable=True
    )
    new_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    steps_saved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_saved: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
