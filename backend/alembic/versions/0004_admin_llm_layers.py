"""admin flag + llm_layers table

Revision ID: 0004_admin_llm_layers
Revises: 0003_sitedoc_tables
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_admin_llm_layers"
down_revision = "0003_sitedoc_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"))
    op.alter_column("users", "is_admin", server_default=None)
    op.execute("UPDATE users SET is_admin = true WHERE email = 'gommeux@gmail.com'")

    op.create_table(
        "llm_layers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("layer_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_llm_layers_layer_key", "llm_layers", ["layer_key"], unique=True)


def downgrade() -> None:
    op.drop_table("llm_layers")
    op.drop_column("users", "is_admin")
