"""prevent allocated task overlaps

Revision ID: 9f4b1a7c3d2e
Revises: e8f2a4c9d013
Create Date: 2026-05-26 19:30:00.000000
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9f4b1a7c3d2e"
down_revision = "e8f2a4c9d013"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "allocated_task_no_user_overlap"


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE allocated_tasks
        ADD CONSTRAINT {CONSTRAINT_NAME}
        EXCLUDE USING gist (
            user_id WITH =,
            tsrange(scheduled_start, scheduled_end, '[)') WITH &&
        )
        """
    )


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    op.execute(f"ALTER TABLE allocated_tasks DROP CONSTRAINT {CONSTRAINT_NAME}")
