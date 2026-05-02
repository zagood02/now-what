from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.enums import PlanItemStatus, PlanStatus


class AIPlan(Base, TimestampMixin):
    __tablename__ = "ai_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    recommendations_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    raw_plan_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    llm_mode: Mapped[str] = mapped_column(String(64), default="template-fallback", nullable=False)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus), default=PlanStatus.active, nullable=False)

    user = relationship("User", back_populates="ai_plans")
    goal = relationship("Goal", back_populates="plans")
    items = relationship("AIPlanItem", back_populates="plan", cascade="all, delete-orphan")


class AIPlanItem(Base, TimestampMixin):
    __tablename__ = "ai_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    ai_plan_id: Mapped[int] = mapped_column(ForeignKey("ai_plans.id", ondelete="CASCADE"), index=True, nullable=False)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(80), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(default=60, nullable=False)
    priority: Mapped[int] = mapped_column(default=2, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_schedulable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    status: Mapped[PlanItemStatus] = mapped_column(
        Enum(PlanItemStatus),
        default=PlanItemStatus.suggested,
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    plan = relationship("AIPlan", back_populates="items")
    user = relationship("User", back_populates="ai_plan_items")
