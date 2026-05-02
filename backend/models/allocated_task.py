from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class AllocatedTask(Base, TimestampMixin):
    __tablename__ = "allocated_tasks"
    __table_args__ = (
        CheckConstraint("scheduled_end > scheduled_start", name="allocated_task_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    flexible_task_id: Mapped[int] = mapped_column(
        ForeignKey("flexible_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="allocated_tasks")
    flexible_task = relationship("FlexibleTask", back_populates="allocations")
