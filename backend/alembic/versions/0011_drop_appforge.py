"""Drop AppForge (app-builder) tables and stale LLM layer rows.

Removes the AI app-builder product: projects, deploy pipeline, ML patterns,
stack presets and project backlog. SiteDoc (sites/tasks/servers) is untouched.

This migration is destructive and not reversible (downgrade is a no-op).
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


# llm_layers rows seeded for the removed AppForge / deploy layers.
_REMOVED_LAYER_KEYS = (
    "code_gen", "mockup", "phase_1", "phase_2", "phase_3", "phase_4", "auto_fix",
)


def upgrade() -> None:
    # 1. Drop tables (children with FKs to `projects` first).
    op.execute("DROP TABLE IF EXISTS backlog_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS deploy_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS ml_patterns CASCADE")
    op.execute("DROP TABLE IF EXISTS stack_presets CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")

    # 2. Remove stale per-layer config rows for deleted layers.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM llm_layers WHERE layer_key IN :keys"
        ).bindparams(sa.bindparam("keys", expanding=True)),
        {"keys": list(_REMOVED_LAYER_KEYS)},
    )


def downgrade() -> None:
    # AppForge removal is irreversible — the dropped tables held generated-app
    # state with no recovery path. Intentionally a no-op.
    pass
