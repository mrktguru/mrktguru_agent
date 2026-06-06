"""WORKFLOWS.md: typed spec + upsell suggestions on tasks.

Adds two JSONB columns to the tasks table:
  - spec:   typed *_SPEC.json artifact (BOT_SPEC, SITE_SPEC, AI_SPEC, …) generated
            before estimation for generative task types.
  - upsell: list of follow-up suggestions generated after task completion.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("spec", postgresql.JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("upsell", postgresql.JSONB(), nullable=True))
    op.create_index(
        "idx_tasks_spec_not_null", "tasks", ["id"],
        postgresql_where=sa.text("spec IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_spec_not_null", table_name="tasks")
    op.drop_column("tasks", "upsell")
    op.drop_column("tasks", "spec")
