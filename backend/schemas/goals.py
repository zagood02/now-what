from datetime import date, datetime

from pydantic import BaseModel, Field

from backend.models.enums import GoalCategory, GoalStatus, PlanItemStatus, PlanStatus
from backend.schemas.base import ORMModel


class GoalCreate(BaseModel):
    user_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: GoalCategory
    status: GoalStatus = GoalStatus.draft
    target_date: date | None = None
    details_json: dict = Field(default_factory=dict)
    answers_json: dict = Field(default_factory=dict)


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: GoalCategory | None = None
    status: GoalStatus | None = None
    target_date: date | None = None
    details_json: dict | None = None
    answers_json: dict | None = None


class GoalRead(ORMModel):
    id: int
    user_id: int
    title: str
    description: str | None
    category: GoalCategory
    status: GoalStatus
    target_date: date | None
    details_json: dict
    answers_json: dict
    created_at: datetime
    updated_at: datetime


class AIPlanItemRead(ORMModel):
    id: int
    ai_plan_id: int
    goal_id: int
    user_id: int
    title: str
    description: str | None
    item_type: str
    estimated_minutes: int
    priority: int
    target_date: date | None
    is_schedulable: bool
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    status: PlanItemStatus
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class AIPlanRead(ORMModel):
    id: int
    user_id: int
    goal_id: int
    summary: str
    strategy_json: dict
    recommendations_json: dict
    raw_plan_json: dict
    llm_mode: str
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
    items: list[AIPlanItemRead] = Field(default_factory=list)


class GoalDetailRead(GoalRead):
    plans: list[AIPlanRead] = Field(default_factory=list)
