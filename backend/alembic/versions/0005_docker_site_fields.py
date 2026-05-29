"""add Docker fields to sites table

Revision ID: 0005_docker_site_fields
Revises: 0004_admin_llm_layers
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_docker_site_fields"
down_revision = "0004_admin_llm_layers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("is_docker", sa.Boolean(), nullable=True))
    op.add_column("sites", sa.Column("docker_compose_dir", sa.String(), nullable=True))
    op.add_column("sites", sa.Column("docker_service_name", sa.String(), nullable=True))
    op.add_column("sites", sa.Column("docker_container_name", sa.String(), nullable=True))
    op.add_column("sites", sa.Column("framework", sa.String(), nullable=True))
    op.add_column("sites", sa.Column("needs_rebuild", sa.Boolean(), nullable=True))


def downgrade() -> None:
    for col in ["is_docker", "docker_compose_dir", "docker_service_name",
                "docker_container_name", "framework", "needs_rebuild"]:
        op.drop_column("sites", col)
