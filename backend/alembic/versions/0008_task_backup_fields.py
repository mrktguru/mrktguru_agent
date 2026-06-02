"""Add backup_available and estimated_minutes to tasks."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("backup_available", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("tasks", sa.Column("estimated_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "estimated_minutes")
    op.drop_column("tasks", "backup_available")
