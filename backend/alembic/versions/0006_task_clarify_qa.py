"""Add clarify_qa JSONB to tasks for dialog history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005_docker_site_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("clarify_qa", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "clarify_qa")
