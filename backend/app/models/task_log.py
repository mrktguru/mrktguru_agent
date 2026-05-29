"""TaskLog model — streaming execution log for a task."""
import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class TaskLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "task_logs"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )

    # Which subtask index this log belongs to (None = overall task log)
    subtask_index: Mapped[int | None] = mapped_column(nullable=True)

    step: Mapped[str | None] = mapped_column(String, nullable=True)
    # running | success | error | rollback
    status: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[float | None] = mapped_column(Float, nullable=True)
