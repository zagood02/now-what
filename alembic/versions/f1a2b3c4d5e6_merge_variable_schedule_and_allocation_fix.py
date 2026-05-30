"""merge variable_schedules migration branch and allocated task overlap fix branch

Revision ID: f1a2b3c4d5e6
Revises: 9f4b1a7c3d2e, e9f1a2b3c4d5
Create Date: 2026-05-31 00:00:00.000000
"""
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = ("9f4b1a7c3d2e", "e9f1a2b3c4d5")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
