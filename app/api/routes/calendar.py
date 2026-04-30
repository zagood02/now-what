from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.db.session import get_db_session
from app.schemas.calendar import CalendarResponse
from app.services.calendar import CalendarService

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
    return calendar_service.build(session, user_id=user_id, start=start, end=end)
