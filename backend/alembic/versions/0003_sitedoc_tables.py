"""add SiteDoc tables: sites, tasks, task_logs, token_transactions + user credits

Revision ID: 0003_sitedoc_tables
Revises: 0002_user_plan
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_sitedoc_tables"
down_revision = "0002_user_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add credit columns to users
    op.add_column("users", sa.Column("token_credits", sa.Float(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("token_credits_monthly", sa.Float(), nullable=False, server_default="0"))
    op.alter_column("users", "token_credits", server_default=None)
    op.alter_column("users", "token_credits_monthly", server_default=None)

    # sites table
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        # SSH
        sa.Column("ssh_host", sa.String(), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("ssh_user", sa.String(), nullable=False),
        sa.Column("auth_type", sa.String(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        # CMS / stack
        sa.Column("cms", sa.String(), nullable=True),
        sa.Column("cms_version", sa.String(), nullable=True),
        sa.Column("php_version", sa.String(), nullable=True),
        sa.Column("web_server", sa.String(), nullable=True),
        sa.Column("server_os", sa.String(), nullable=True),
        sa.Column("site_root_path", sa.String(), nullable=True),
        sa.Column("file_structure", postgresql.JSONB(), nullable=True),
        sa.Column("installed_plugins", postgresql.JSONB(), nullable=True),
        # Audit
        sa.Column("audit_score", sa.Integer(), nullable=True),
        sa.Column("audit_report", postgresql.JSONB(), nullable=True),
        # Monitoring
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("uptime_percent", sa.Float(), nullable=True),
    )
    op.create_index("ix_sites_user_id", "sites", ["user_id"])

    # tasks table
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("tz_text", sa.Text(), nullable=True),
        sa.Column("reference_urls", postgresql.JSONB(), nullable=True),
        sa.Column("attachments", postgresql.JSONB(), nullable=True),
        sa.Column("subtasks", postgresql.JSONB(), nullable=True),
        sa.Column("estimated_credits", sa.Float(), nullable=True),
        sa.Column("actual_credits", sa.Float(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("changed_files", postgresql.JSONB(), nullable=True),
        sa.Column("screenshot_before", sa.Text(), nullable=True),
        sa.Column("screenshot_after", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_tasks_site_id", "tasks", ["site_id"])
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])

    # task_logs table
    op.create_table(
        "task_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subtask_index", sa.Integer(), nullable=True),
        sa.Column("step", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("tokens_used", sa.Float(), nullable=True),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])

    # token_transactions table
    op.create_table(
        "token_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("credits_delta", sa.Float(), nullable=False),
        sa.Column("credits_balance", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_token_transactions_user_id", "token_transactions", ["user_id"])


def downgrade() -> None:
    op.drop_table("token_transactions")
    op.drop_table("task_logs")
    op.drop_table("tasks")
    op.drop_table("sites")
    op.drop_column("users", "token_credits_monthly")
    op.drop_column("users", "token_credits")
