from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class VariableSchedule(Base, TimestampMixin):
    __tablename__ = "variable_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    color_key: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    fatigue: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    details_json: Mapped[dict] = mapped_column(JSON(), nullable=False, default=dict)

    user = relationship("User", back_populates="variable_schedules")

    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_variable_schedules_time_window"),
    )
