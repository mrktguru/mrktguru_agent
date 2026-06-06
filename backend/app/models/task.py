"""Task model — a TZ (technical specification) submitted by user for a site."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # User input
    title: Mapped[str | None] = mapped_column(String, nullable=True)  # auto-generated from TZ
    tz_text: Mapped[str | None] = mapped_column(Text, nullable=True)   # raw TZ pasted by user
    reference_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)   # URLs to screenshot
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)      # base64 images

    # Parsed subtasks (list of {id, title, description, files_to_touch, estimated_credits, risk})
    subtasks: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── Two-level triage + typed tracks (AGENT_ARCHITECTURE.md) ──────────────
    intent: Mapped[str | None] = mapped_column(String, nullable=True)       # action|fix|info|ops|control|reject
    task_type: Mapped[str | None] = mapped_column(String, nullable=True)    # tweak|integration|parser|bugfix|...
    # Typed tracks: [{track_id, intent, type, summary, depends_on[], risk, integration?, subtasks[]}]
    tracks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Triage decision log: {intent, type, confidence, reasoning}
    triage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Pause-for-human: {message, required_fields[], track_id} when status=waiting_for_user
    pending_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Serialized agent tool-use thread, to resume the loop after a pause
    agent_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Answer text for info-intent tasks (status=answered, no edits)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Estimation
    estimated_credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)  # high|medium|low

    # ── Two-phase billing (CREDIT_MECHANICS.md §5) ───────────────────────────
    reserved_credits: Mapped[float | None] = mapped_column(Float, nullable=True)   # frozen on approve (estimate×1.3)
    complexity: Mapped[str | None] = mapped_column(String, nullable=True)          # low|medium|high|unknown
    overage_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overage_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status flow: pending → estimated → approved → running → done | failed | rolled_back
    # plus: clarifying, rolling_back, waiting_for_user, answered, rejected, stalled (budget HARD_STOP)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    # Clarification dialog history: [{questions: [...], answer: str}]
    clarify_qa: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Result
    changed_files: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Per-file line diff stats: {"<path>": {"added": int, "removed": int}}
    file_diffs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    screenshot_before: Mapped[str | None] = mapped_column(Text, nullable=True)  # base64 or URL
    screenshot_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # True after a successful run while file backups still exist (enables manual rollback).
    backup_available: Mapped[bool] = mapped_column(default=False, nullable=False)
