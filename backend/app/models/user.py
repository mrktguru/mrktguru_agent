"""User model."""
from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    google_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, default="UTC", nullable=False)
    plan: Mapped[str] = mapped_column(String, default="starter", nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ── Credit balance (CREDIT_MECHANICS.md §9.1) ────────────────────────────
    # token_credits / token_credits_monthly already exist in the DB (migration
    # 0003) but were never mapped — code read them via getattr. Mapping them
    # lets SQLAlchemy UPDATE the balance transactionally.
    token_credits: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)          # bought / available pool
    token_credits_monthly: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # plan allotment
    frozen_credits: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)         # held under active tasks
