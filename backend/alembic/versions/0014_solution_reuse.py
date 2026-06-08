"""Solution reuse: solutions, patterns, reuse_log tables with pgvector.

Implements SOLUTION_REUSE.md §1.3 schema.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "solutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),        # curated_skill | accumulated
        sa.Column("level", sa.String(12), nullable=False),         # snippet | template | pattern
        sa.Column("task_type", sa.String(32), nullable=True),
        sa.Column("stack", sa.String(64), nullable=True),
        sa.Column("stack_version", sa.String(32), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("solution_body", sa.Text, nullable=True),
        sa.Column("spec", postgresql.JSONB, nullable=True),
        sa.Column("required_deps", postgresql.JSONB, nullable=True),
        sa.Column("required_env", postgresql.JSONB, nullable=True),
        sa.Column("expected_files", postgresql.JSONB, nullable=True),
        sa.Column("key_patterns", postgresql.JSONB, nullable=True),
        sa.Column("success_rate", sa.Float, server_default="0.95", nullable=False),
        sa.Column("reuse_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("fail_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("avg_steps_saved", sa.Float, nullable=True),
        sa.Column("avg_credits_saved", sa.Float, nullable=True),
        sa.Column("trusted", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_to_skill", sa.Boolean, server_default="false", nullable=False),
    )
    # Add vector column separately (pgvector type)
    op.execute("ALTER TABLE solutions ADD COLUMN embedding vector(1536)")
    op.execute("CREATE INDEX idx_sol_type_stack ON solutions (task_type, stack)")
    op.execute("CREATE INDEX idx_sol_quality ON solutions (success_rate DESC, reuse_count DESC)")
    # IVFFlat index requires rows; created lazily by seeder after data is loaded.

    op.create_table(
        "patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_type", sa.String(32), nullable=True),
        sa.Column("stack", sa.String(64), nullable=True),
        sa.Column("lesson", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, server_default="0.5", nullable=False),
        sa.Column("observed_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.execute("ALTER TABLE patterns ADD COLUMN embedding vector(1536)")

    op.create_table(
        "reuse_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("solution_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("solutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("new_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("similarity", sa.Float, nullable=True),
        sa.Column("action", sa.String(16), nullable=True),      # apply|adapt|reference|generate
        sa.Column("outcome", sa.String(16), nullable=True),     # success|partial|failed
        sa.Column("steps_saved", sa.Integer, nullable=True),
        sa.Column("credits_saved", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reuse_log")
    op.drop_table("patterns")
    op.drop_table("solutions")
