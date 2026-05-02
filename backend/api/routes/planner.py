from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import require_user
from backend.core.config import settings
from backend.db.session import get_db_session
from backend.schemas.goals import AIPlanItemRead
from backend.schemas.planning import AllocateRequest, AllocateResponse
from backend.schemas.schedules import AllocatedTaskRead
from backend.services.allocation import AllocationService

router = APIRouter(prefix="/planner", tags=["planner"])
allocation_service = AllocationService()


def _parse_default_time(raw_value: str) -> time:
    return datetime.strptime(raw_value, "%H:%M").time()


@router.post("/allocate", response_model=AllocateResponse)
def allocate_schedule(
    payload: AllocateRequest,
    session: Session = Depends(get_db_session),
) -> AllocateResponse:
    require_user(session, payload.user_id)
    if payload.range_end <= payload.range_start:
        raise HTTPException(status_code=400, detail="range_end must be after range_start.")

    day_start = payload.day_start or _parse_default_time(settings.default_day_start)
    day_end = payload.day_end or _parse_default_time(settings.default_day_end)
    if day_end <= day_start:
        raise HTTPException(status_code=400, detail="day_end must be after day_start.")

    result = allocation_service.allocate(
        session,
        user_id=payload.user_id,
        range_start=payload.range_start,
        range_end=payload.range_end,
        day_start=day_start,
        day_end=day_end,
        clear_existing=payload.clear_existing,
    )
    session.commit()

    return AllocateResponse(
        allocated_tasks=[AllocatedTaskRead.model_validate(item) for item in result.allocated_tasks],
        scheduled_plan_items=[AIPlanItemRead.model_validate(item) for item in result.scheduled_plan_items],
        unscheduled_task_ids=result.unscheduled_task_ids,
        unscheduled_plan_item_ids=result.unscheduled_plan_item_ids,
        message="Allocation completed with greedy scheduling.",
    )
