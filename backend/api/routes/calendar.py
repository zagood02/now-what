from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.config import settings
from backend.core.timezone import normalize_to_kst_naive
from backend.db.session import get_db_session
from backend.models.user import User
from backend.schemas.calendar import CalendarResponse
from backend.services.calendar import CalendarService

router = APIRouter(tags=["calendar"])
calendar_service = CalendarService()
logger = logging.getLogger(__name__)


@router.get("/calendar", response_model=CalendarResponse)
def get_calendar(
    start: datetime = Query(...),
    end: datetime = Query(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> CalendarResponse:
    user_id = current_user.id
    start = normalize_to_kst_naive(start)
    end = normalize_to_kst_naive(end)
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start.")
    if end - start > timedelta(days=settings.max_calendar_range_days):
        raise HTTPException(
            status_code=400,
            detail=f"Calendar range cannot exceed {settings.max_calendar_range_days} days.",
        )
    try:
        return calendar_service.build(session, user_id=user_id, start=start, end=end)
    except Exception as exc:
        logger.exception("Calendar build failed for user %s.", user_id)
        raise HTTPException(status_code=500, detail="Calendar generation failed.") from exc
