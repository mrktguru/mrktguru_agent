"""Add figma_token_enc to users table."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("figma_token_enc", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "figma_token_enc")
