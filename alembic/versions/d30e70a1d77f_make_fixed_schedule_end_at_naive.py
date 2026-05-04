"""make fixed schedule end_at naive

Revision ID: d30e70a1d77f
Revises: b7f5b58b2a10
Create Date: 2026-05-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d30e70a1d77f"
down_revision = "b7f5b58b2a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "fixed_schedules",
        "end_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="end_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "fixed_schedules",
        "end_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        postgresql_using="end_at AT TIME ZONE 'UTC'",
    )
