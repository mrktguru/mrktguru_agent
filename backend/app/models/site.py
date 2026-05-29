"""Site model — user's existing website accessible via SSH."""
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDMixin


class Site(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Basic info
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)

    # SSH access
    ssh_host: Mapped[str] = mapped_column(String, nullable=False)
    ssh_port: Mapped[int] = mapped_column(default=22, nullable=False)
    ssh_user: Mapped[str] = mapped_column(String, nullable=False)
    # 'password' | 'platform_key'
    auth_type: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)

    # CMS / tech stack (filled after scan)
    cms: Mapped[str | None] = mapped_column(String, nullable=True)          # wordpress|joomla|bitrix|custom
    cms_version: Mapped[str | None] = mapped_column(String, nullable=True)
    php_version: Mapped[str | None] = mapped_column(String, nullable=True)
    web_server: Mapped[str | None] = mapped_column(String, nullable=True)   # nginx|apache
    server_os: Mapped[str | None] = mapped_column(String, nullable=True)
    site_root_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_structure: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    installed_plugins: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Audit results
    audit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audit_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Monitoring
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)  # active|error|scanning
    uptime_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
