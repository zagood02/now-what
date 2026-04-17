from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import GoalCategory, GoalStatus


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[GoalCategory] = mapped_column(Enum(GoalCategory), index=True, nullable=False)
    status: Mapped[GoalStatus] = mapped_column(Enum(GoalStatus), default=GoalStatus.draft, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    answers_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="goals")
    plans = relationship("AIPlan", back_populates="goal", cascade="all, delete-orphan")
