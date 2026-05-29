"""TokenTransaction model — credit ledger."""
import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class TokenTransaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "token_transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )

    # charge | refund | purchase | monthly_refill
    type: Mapped[str] = mapped_column(String, nullable=False)
    credits_delta: Mapped[float] = mapped_column(Float, nullable=False)   # negative = charge
    credits_balance: Mapped[float] = mapped_column(Float, nullable=False)  # balance after
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
