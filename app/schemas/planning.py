from datetime import datetime, time

from pydantic import BaseModel, Field

from app.models.enums import GoalCategory
from app.schemas.goals import AIPlanItemRead, AIPlanRead, GoalRead
from app.schemas.schedules import AllocatedTaskRead


class GoalQuestion(BaseModel):
    key: str
    prompt: str
    answer_type: str
    required: bool = True
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)


class GoalIntakeRequest(BaseModel):
    text: str = Field(min_length=1)
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


class GoalCompleteRequest(BaseModel):
    user_id: int
    text: str = Field(min_length=1)
    category: GoalCategory | None = None
    answers_json: dict = Field(default_factory=dict)
    replace_existing: bool = True


class GoalCompleteResponse(BaseModel):
    goal: GoalRead
    plan: AIPlanRead
    reasoning: str
    questions: list[GoalQuestion]
    saved: bool = True
    llm_mode: str


class AllocateRequest(BaseModel):
    user_id: int
    range_start: datetime
    range_end: datetime
    day_start: time | None = None
    day_end: time | None = None
    clear_existing: bool = False


class AllocateResponse(BaseModel):
    allocated_tasks: list[AllocatedTaskRead]
    scheduled_plan_items: list[AIPlanItemRead]
    unscheduled_task_ids: list[int]
    unscheduled_plan_item_ids: list[int]
    message: str
