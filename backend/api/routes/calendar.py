from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.deps import require_user
from backend.db.session import get_db_session
from backend.schemas.calendar import CalendarResponse
from backend.services.calendar import CalendarService

router = APIRouter(tags=["calendar"])
calendar_service = CalendarService()


@router.get("/calendar", response_model=CalendarResponse)
def get_calendar(
    user_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    session: Session = Depends(get_db_session),
) -> CalendarResponse:
    require_user(session, user_id)
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start.")
    # Convert to naive datetime if timezone-aware
    if start.tzinfo is not None:
        start = start.replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    try:
        return calendar_service.build(session, user_id=user_id, start=start, end=end)
    except Exception as e:
        # Return empty calendar on error to prevent frontend crashes
        from backend.schemas.calendar import CalendarResponse
        return CalendarResponse(
            user_id=user_id,
            start=start,
            end=end,
            events=[],
            totals={"fixed_schedule": 0, "allocated_task": 0, "ai_plan_item": 0}
        )
