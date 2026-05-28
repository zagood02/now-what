from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator

from backend.models.enums import GoalCategory
from backend.schemas.goals import AIPlanItemRead, AIPlanRead, GoalRead
from backend.schemas.schedules import AllocatedTaskRead


class GoalQuestion(BaseModel):
    key: str
    prompt: str
    answer_type: str
    required: bool = True
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)


class GoalTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class GoalIntakeRequest(GoalTextRequest):
    category: GoalCategory | None = None


class GoalDraftSuggestion(BaseModel):
    title: str
    description: str | None = None
    category: GoalCategory
    details_json: dict = Field(default_factory=dict)
    answers_json: dict = Field(default_factory=dict)


class GoalIntakeResponse(BaseModel):
    goal: GoalDraftSuggestion
    reasoning: str
    questions: list[GoalQuestion]


class GoalCompleteRequest(GoalTextRequest):
    category: GoalCategory | None = None
    answers_json: dict = Field(default_factory=dict)
    replace_existing: bool = False


class GoalCompleteResponse(BaseModel):
    goal: GoalRead
    plan: AIPlanRead
    reasoning: str
    questions: list[GoalQuestion]
    saved: bool = True
    llm_mode: str


class AllocateRequest(BaseModel):
    range_start: datetime
    range_end: datetime
    day_start: time | None = None
    day_end: time | None = None
    buffer_minutes: int | None = Field(default=None, ge=0)
    max_auto_minutes_per_day: int | None = Field(default=None, gt=0)
    clear_existing: bool = True


class AllocateResponse(BaseModel):
    allocated_tasks: list[AllocatedTaskRead]
    scheduled_plan_items: list[AIPlanItemRead]
    unscheduled_task_ids: list[int]
    unscheduled_plan_item_ids: list[int]
    message: str
