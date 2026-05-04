from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.enums import FlexibleTaskStatus
from backend.schemas.base import ORMModel


class FlexibleTaskCreate(BaseModel):
    user_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    estimated_minutes: int = Field(gt=0)
    min_session_minutes: int = Field(default=30, gt=0)
    preferred_session_minutes: int = Field(default=60, gt=0)
    max_minutes_per_day: int = Field(default=180, gt=0)
    priority: int = Field(default=2, ge=1, le=3)
    due_at: datetime | None = None
    details_json: dict = Field(default_factory=dict)


class FlexibleTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    min_session_minutes: int | None = Field(default=None, gt=0)
    preferred_session_minutes: int | None = Field(default=None, gt=0)
    max_minutes_per_day: int | None = Field(default=None, gt=0)
    priority: int | None = Field(default=None, ge=1, le=3)
    due_at: datetime | None = None
    status: FlexibleTaskStatus | None = None
    details_json: dict | None = None


class FlexibleTaskRead(ORMModel):
    id: int
    user_id: int
    title: str
    description: str | None
    estimated_minutes: int
    min_session_minutes: int
    preferred_session_minutes: int
    max_minutes_per_day: int
    priority: int
    due_at: datetime | None
    status: FlexibleTaskStatus
    details_json: dict
    allocated_minutes: int
    remaining_minutes: int
    created_at: datetime
    updated_at: datetime
