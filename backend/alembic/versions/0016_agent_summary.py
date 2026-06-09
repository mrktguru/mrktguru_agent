"""Add agent_summary to tasks table."""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("agent_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "agent_summary")
