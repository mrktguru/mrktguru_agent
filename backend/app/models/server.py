"""Server (user's VPS) model."""
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class Server(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "servers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    ip: Mapped[str] = mapped_column(String, nullable=False)
    ssh_user: Mapped[str] = mapped_column(String, nullable=False)
    ssh_port: Mapped[int] = mapped_column(default=22, nullable=False)

    # 'password' | 'platform_key'
    auth_type: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)

    os_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    hardware_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    installed_software: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
