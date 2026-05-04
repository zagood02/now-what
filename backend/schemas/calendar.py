from datetime import datetime

from pydantic import BaseModel, Field


class CalendarEventRead(BaseModel):
    id: str
    source_type: str
    source_id: int
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    status: str
    metadata_json: dict = Field(default_factory=dict)


class CalendarResponse(BaseModel):
    user_id: int
    start: datetime
    end: datetime
    events: list[CalendarEventRead]
    totals: dict[str, int]
