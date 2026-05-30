"""create variable_schedules table

Revision ID: e9f1a2b3c4d5
Revises: e8f2a4c9d013
Create Date: 2026-05-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e9f1a2b3c4d5"
down_revision = "e8f2a4c9d013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "variable_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("is_all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("color_key", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fatigue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("end_at > start_at", name="ck_variable_schedules_time_window"),
    )
    op.create_index(op.f("ix_variable_schedules_user_id"), "variable_schedules", ["user_id"])
    op.create_index(op.f("ix_variable_schedules_start_at"), "variable_schedules", ["start_at"])
    op.create_index(op.f("ix_variable_schedules_end_at"), "variable_schedules", ["end_at"])

    op.execute(
        """
        INSERT INTO variable_schedules (
            user_id,
            title,
            description,
            start_at,
            end_at,
            is_all_day,
            color_key,
            fatigue,
            status,
            details_json,
            created_at,
            updated_at
        )
        SELECT
            user_id,
            title,
            description,
            (details_json::jsonb->>'scheduled_start')::timestamp,
            (details_json::jsonb->>'scheduled_end')::timestamp,
            false,
            COALESCE((details_json::jsonb->>'color_key')::int, 0),
            0,
            CASE
                WHEN status = 'completed' THEN 'completed'
                WHEN status = 'cancelled' THEN 'failed'
                ELSE 'pending'
            END,
            (details_json::jsonb - 'scheduled_start' - 'scheduled_end')::json,
            created_at,
            updated_at
        FROM flexible_tasks
        WHERE details_json::jsonb ? 'scheduled_start'
          AND details_json::jsonb ? 'scheduled_end'
        """
    )

    op.execute(
        """
        UPDATE flexible_tasks
        SET status = 'cancelled'
        WHERE details_json::jsonb ? 'scheduled_start'
          AND details_json::jsonb ? 'scheduled_end'
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_variable_schedules_end_at"), table_name="variable_schedules")
    op.drop_index(op.f("ix_variable_schedules_start_at"), table_name="variable_schedules")
    op.drop_index(op.f("ix_variable_schedules_user_id"), table_name="variable_schedules")
    op.drop_table("variable_schedules")
