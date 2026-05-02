from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class FixedSchedule(Base, TimestampMixin):
    __tablename__ = "fixed_schedules"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="fixed_schedule_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=일요일, 1=월요일, ..., 6=토요일

    user = relationship("User", back_populates="fixed_schedules")
