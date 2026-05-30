from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, require_owned_resource
from backend.core.timezone import normalize_optional_to_kst_naive, normalize_to_kst_naive
from backend.db.session import get_db_session
from backend.models.user import User
from backend.models.variable_schedule import VariableSchedule
from backend.schemas.base import Message
from backend.schemas.schedules import (
    VariableScheduleCreate,
    VariableScheduleRead,
    VariableScheduleUpdate,
)

router = APIRouter(prefix="/schedules/variable", tags=["variable-schedules"])


def _validate_window(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at.")


def _validate_query_range(start: datetime | None, end: datetime | None) -> None:
    if not start or not end:
        return
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start.")


@router.post("", response_model=VariableScheduleRead, status_code=status.HTTP_201_CREATED)
def create_variable_schedule(
    payload: VariableScheduleCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> VariableSchedule:
    start_at = normalize_to_kst_naive(payload.start_at)
    end_at = normalize_to_kst_naive(payload.end_at)
    _validate_window(start_at, end_at)

    schedule = VariableSchedule(
        **payload.model_dump(exclude={"start_at", "end_at"}),
        user_id=current_user.id,
        start_at=start_at,
        end_at=end_at,
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.get("", response_model=list[VariableScheduleRead])
def list_variable_schedules(
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[VariableSchedule]:
    user_id = current_user.id
    start = normalize_optional_to_kst_naive(start)
    end = normalize_optional_to_kst_naive(end)
    _validate_query_range(start, end)

    conditions = [VariableSchedule.user_id == user_id]
    if start or end:
        range_conditions = []
        if start:
            range_conditions.append(VariableSchedule.end_at > start)
        if end:
            range_conditions.append(VariableSchedule.start_at < end)
        conditions.append(and_(*range_conditions))

    query = select(VariableSchedule).where(and_(*conditions)).order_by(VariableSchedule.start_at.asc())
    return session.scalars(query).all()


@router.get("/{schedule_id}", response_model=VariableScheduleRead)
def get_variable_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> VariableSchedule:
    return require_owned_resource(
        session,
        VariableSchedule,
        schedule_id,
        current_user.id,
        detail="Variable schedule not found.",
    )


@router.patch("/{schedule_id}", response_model=VariableScheduleRead)
def update_variable_schedule(
    schedule_id: int,
    payload: VariableScheduleUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> VariableSchedule:
    schedule = require_owned_resource(
        session,
        VariableSchedule,
        schedule_id,
        current_user.id,
        detail="Variable schedule not found.",
    )

    updates = payload.model_dump(exclude_unset=True)
    if "start_at" in updates:
        updates["start_at"] = normalize_to_kst_naive(updates["start_at"])
    if "end_at" in updates:
        updates["end_at"] = normalize_to_kst_naive(updates["end_at"])

    next_start = updates.get("start_at", schedule.start_at)
    next_end = updates.get("end_at", schedule.end_at)
    _validate_window(next_start, next_end)

    for field, value in updates.items():
        setattr(schedule, field, value)

    session.commit()
    session.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", response_model=Message)
def delete_variable_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Message:
    schedule = require_owned_resource(
        session,
        VariableSchedule,
        schedule_id,
        current_user.id,
        detail="Variable schedule not found.",
    )

    session.delete(schedule)
    session.commit()
    return Message(detail="Variable schedule deleted.")
