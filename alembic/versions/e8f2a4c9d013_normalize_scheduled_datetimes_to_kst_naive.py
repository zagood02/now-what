"""normalize scheduled datetimes to kst naive

Revision ID: e8f2a4c9d013
Revises: d30e70a1d77f
Create Date: 2026-05-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e8f2a4c9d013"
down_revision = "d30e70a1d77f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "flexible_tasks",
        "due_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="due_at AT TIME ZONE 'Asia/Seoul'",
    )
    op.execute(
        "ALTER TABLE allocated_tasks DROP CONSTRAINT ck_allocated_tasks_allocated_task_window"
    )
    op.alter_column(
        "allocated_tasks",
        "scheduled_start",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="scheduled_start AT TIME ZONE 'Asia/Seoul'",
    )
    op.alter_column(
        "allocated_tasks",
        "scheduled_end",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="scheduled_end AT TIME ZONE 'Asia/Seoul'",
    )
    op.execute(
        "ALTER TABLE allocated_tasks ADD CONSTRAINT ck_allocated_tasks_allocated_task_window CHECK (scheduled_end > scheduled_start)"
    )
    op.alter_column(
        "ai_plan_items",
        "scheduled_start",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="scheduled_start AT TIME ZONE 'Asia/Seoul'",
    )
    op.alter_column(
        "ai_plan_items",
        "scheduled_end",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="scheduled_end AT TIME ZONE 'Asia/Seoul'",
    )


def downgrade() -> None:
    op.alter_column(
        "ai_plan_items",
        "scheduled_end",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
        postgresql_using="scheduled_end AT TIME ZONE 'Asia/Seoul'",
    )
    op.alter_column(
        "ai_plan_items",
        "scheduled_start",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
        postgresql_using="scheduled_start AT TIME ZONE 'Asia/Seoul'",
    )
    op.alter_column(
        "allocated_tasks",
        "scheduled_end",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        postgresql_using="scheduled_end AT TIME ZONE 'Asia/Seoul'",
    )
    op.alter_column(
        "allocated_tasks",
        "scheduled_start",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        postgresql_using="scheduled_start AT TIME ZONE 'Asia/Seoul'",
    )
    op.alter_column(
        "flexible_tasks",
        "due_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
        postgresql_using="due_at AT TIME ZONE 'Asia/Seoul'",
    )
