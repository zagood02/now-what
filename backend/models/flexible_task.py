from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.enums import FlexibleTaskStatus


class FlexibleTask(Base, TimestampMixin):
    __tablename__ = "flexible_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(nullable=False)
    min_session_minutes: Mapped[int] = mapped_column(default=30, nullable=False)
    preferred_session_minutes: Mapped[int] = mapped_column(default=60, nullable=False)
    max_minutes_per_day: Mapped[int] = mapped_column(default=180, nullable=False)
    priority: Mapped[int] = mapped_column(default=2, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    status: Mapped[FlexibleTaskStatus] = mapped_column(
        Enum(FlexibleTaskStatus),
        default=FlexibleTaskStatus.pending,
        nullable=False,
    )
    details_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="flexible_tasks")
    allocations = relationship("AllocatedTask", back_populates="flexible_task", cascade="all, delete-orphan")

    @hybrid_property
    def allocated_minutes(self) -> int:
        return sum(allocation.duration_minutes for allocation in self.allocations)

    @hybrid_property
    def remaining_minutes(self) -> int:
        remaining = self.estimated_minutes - self.allocated_minutes
        return remaining if remaining > 0 else 0
