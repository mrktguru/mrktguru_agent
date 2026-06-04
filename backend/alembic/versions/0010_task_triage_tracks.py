"""Add triage + typed tracks + pause fields to tasks."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("intent", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("task_type", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("tracks", postgresql.JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("triage", postgresql.JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("pending_input", postgresql.JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("agent_state", postgresql.JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("answer_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "answer_text")
    op.drop_column("tasks", "agent_state")
    op.drop_column("tasks", "pending_input")
    op.drop_column("tasks", "triage")
    op.drop_column("tasks", "tracks")
    op.drop_column("tasks", "task_type")
    op.drop_column("tasks", "intent")
