from enum import Enum


class GoalCategory(str, Enum):
    study = "study"
    health = "health"
    work = "work"
    habit = "habit"
    general = "general"


class GoalStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class FlexibleTaskStatus(str, Enum):
    pending = "pending"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class PlanStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class PlanItemStatus(str, Enum):
    suggested = "suggested"
    scheduled = "scheduled"
    completed = "completed"
    skipped = "skipped"
