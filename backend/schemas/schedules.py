from datetime import datetime

from pydantic import BaseModel, Field

from backend.schemas.base import ORMModel


class FixedScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    is_all_day: bool = False
    recurrence_rule: str | None = Field(default=None, max_length=255)
    day_of_week: int | None = Field(default=None, ge=0, le=6)  # 0=일요일, 1=월요일, ..., 6=토요일


class FixedScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_all_day: bool | None = None
    recurrence_rule: str | None = Field(default=None, max_length=255)
    day_of_week: int | None = Field(default=None, ge=0, le=6)


class FixedScheduleRead(ORMModel):
    id: int
    user_id: int
    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime
    is_all_day: bool
    recurrence_rule: str | None
    day_of_week: int | None
    created_at: datetime
    updated_at: datetime


class VariableScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_at: datetime
    end_at: datetime
    is_all_day: bool = False
    color_key: int = 0
    fatigue: int = 0
    status: str = "pending"
    details_json: dict = Field(default_factory=dict)


class VariableScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_all_day: bool | None = None
    color_key: int | None = None
    fatigue: int | None = None
    status: str | None = None
    details_json: dict | None = None


class VariableScheduleRead(ORMModel):
    id: int
    user_id: int
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    is_all_day: bool
    color_key: int
    fatigue: int
    status: str
    details_json: dict
    created_at: datetime
    updated_at: datetime


class AllocatedTaskRead(ORMModel):
    id: int
    user_id: int
    flexible_task_id: int
    title_snapshot: str
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    created_at: datetime
    updated_at: datetime
