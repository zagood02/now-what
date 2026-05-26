from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Seoul", nullable=False)

    fixed_schedules = relationship("FixedSchedule", back_populates="user", cascade="all, delete-orphan")
    flexible_tasks = relationship("FlexibleTask", back_populates="user", cascade="all, delete-orphan")
    allocated_tasks = relationship("AllocatedTask", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    ai_plans = relationship("AIPlan", back_populates="user", cascade="all, delete-orphan")
    ai_plan_items = relationship("AIPlanItem", back_populates="user", cascade="all, delete-orphan")
    auth_accounts = relationship("AuthAccount", back_populates="user", cascade="all, delete-orphan")
