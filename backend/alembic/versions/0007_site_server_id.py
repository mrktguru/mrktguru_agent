"""Link sites to a registered server (sites.server_id)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("server_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_sites_server_id",
        "sites",
        "servers",
        ["server_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sites_server_id", "sites", type_="foreignkey")
    op.drop_column("sites", "server_id")
