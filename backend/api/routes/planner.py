from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, require_owned_resource
from backend.core.config import settings
from backend.core.timezone import normalize_to_kst_naive
from backend.db.session import get_db_session
from backend.models.ai_plan import AIPlanItem
from backend.models.enums import PlanItemStatus
from backend.models.user import User
from backend.schemas.base import Message
from backend.schemas.goals import AIPlanItemRead
from backend.schemas.planning import AllocateRequest, AllocateResponse
from backend.schemas.schedules import AllocatedTaskRead
from backend.services.allocation import AllocationConflictError, AllocationService

router = APIRouter(prefix="/planner", tags=["planner"])
allocation_service = AllocationService()


def _parse_default_time(raw_value: str) -> time:
    return datetime.strptime(raw_value, "%H:%M").time()


@router.post("/allocate", response_model=AllocateResponse)
def allocate_schedule(
    payload: AllocateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AllocateResponse:
    range_start = normalize_to_kst_naive(payload.range_start)
    range_end = normalize_to_kst_naive(payload.range_end)
    if range_end <= range_start:
        raise HTTPException(status_code=400, detail="range_end must be after range_start.")
    if range_end - range_start > timedelta(days=settings.max_allocation_range_days):
        raise HTTPException(
            status_code=400,
            detail=f"Allocation range cannot exceed {settings.max_allocation_range_days} days.",
        )

    day_start = payload.day_start or _parse_default_time(settings.default_day_start)
    day_end = payload.day_end or _parse_default_time(settings.default_day_end)
    if day_end <= day_start:
        raise HTTPException(status_code=400, detail="day_end must be after day_start.")
    buffer_minutes = (
        settings.default_buffer_minutes if payload.buffer_minutes is None else payload.buffer_minutes
    )
    max_auto_minutes_per_day = (
        settings.default_max_auto_minutes_per_day
        if payload.max_auto_minutes_per_day is None
        else payload.max_auto_minutes_per_day
    )

    try:
        with allocation_service.allocation_transaction(session, user_id=current_user.id):
            try:
                result = allocation_service.allocate(
                    session,
                    user_id=current_user.id,
                    range_start=range_start,
                    range_end=range_end,
                    day_start=day_start,
                    day_end=day_end,
                    buffer_minutes=buffer_minutes,
                    max_auto_minutes_per_day=max_auto_minutes_per_day,
                    clear_existing=payload.clear_existing,
                )
                session.commit()
            except (AllocationConflictError, IntegrityError):
                session.rollback()
                raise
    except AllocationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Schedule changed during allocation. Please retry.") from exc

    return AllocateResponse(
        allocated_tasks=[AllocatedTaskRead.model_validate(item) for item in result.allocated_tasks],
        scheduled_plan_items=[AIPlanItemRead.model_validate(item) for item in result.scheduled_plan_items],
        unscheduled_task_ids=result.unscheduled_task_ids,
        unscheduled_plan_item_ids=result.unscheduled_plan_item_ids,
        message="Allocation completed with automatic rescheduling.",
    )


@router.delete("/plan-items/{item_id}/schedule", response_model=AIPlanItemRead)
def unschedule_plan_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AIPlanItem:
    item = require_owned_resource(
        session,
        AIPlanItem,
        item_id,
        current_user.id,
        detail="Plan item not found.",
    )
    if item.status in {PlanItemStatus.completed, PlanItemStatus.skipped}:
        raise HTTPException(status_code=400, detail="Completed or skipped plan items cannot be unscheduled.")

    item.scheduled_start = None
    item.scheduled_end = None
    item.status = PlanItemStatus.suggested
    session.commit()
    session.refresh(item)
    return item


@router.post("/plan-items/{item_id}/skip", response_model=AIPlanItemRead)
def skip_plan_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AIPlanItem:
    item = require_owned_resource(
        session,
        AIPlanItem,
        item_id,
        current_user.id,
        detail="Plan item not found.",
    )
    if item.status == PlanItemStatus.completed:
        raise HTTPException(status_code=400, detail="Completed plan items cannot be skipped.")

    item.scheduled_start = None
    item.scheduled_end = None
    item.status = PlanItemStatus.skipped
    session.commit()
    session.refresh(item)
    return item


@router.delete("/plan-items/{item_id}", response_model=Message)
def delete_plan_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Message:
    item = require_owned_resource(
        session,
        AIPlanItem,
        item_id,
        current_user.id,
        detail="Plan item not found.",
    )
    session.delete(item)
    session.commit()
    return Message(detail="Plan item deleted.")
