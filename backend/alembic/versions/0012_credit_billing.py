"""Credit billing: frozen balance, task reserve/settlement, per-step token metering.

Adds two-phase billing fields (CREDIT_MECHANICS.md). The token_transactions
ledger and users.token_credits* already exist (migration 0003) — only the
frozen balance, task reserve/overage/settlement fields and per-step metering
columns on task_logs are new.
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users — held balance
    op.add_column("users", sa.Column("frozen_credits", sa.Float(), server_default="0", nullable=False))

    # tasks — reserve + overage + settlement
    op.add_column("tasks", sa.Column("reserved_credits", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("complexity", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("overage_approved", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("tasks", sa.Column("overage_amount", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True))

    # task_logs — per-step token metering
    op.add_column("task_logs", sa.Column("model", sa.String(), nullable=True))
    op.add_column("task_logs", sa.Column("step_index", sa.Integer(), nullable=True))
    op.add_column("task_logs", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("task_logs", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("task_logs", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
    op.add_column("task_logs", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))
    op.add_column("task_logs", sa.Column("cost_usd", sa.Float(), nullable=True))
    op.add_column("task_logs", sa.Column("credits", sa.Float(), nullable=True))
    op.create_index("idx_task_logs_model_created", "task_logs", ["model", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_task_logs_model_created", table_name="task_logs")
    for col in ("credits", "cost_usd", "cache_write_tokens", "cache_read_tokens",
                "output_tokens", "input_tokens", "step_index", "model"):
        op.drop_column("task_logs", col)
    for col in ("settled_at", "overage_amount", "overage_approved", "complexity", "reserved_credits"):
        op.drop_column("tasks", col)
    op.drop_column("users", "frozen_credits")
