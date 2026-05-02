from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_owned_resource, require_user
from app.db.session import get_db_session
from app.models.fixed_schedule import FixedSchedule
from app.schemas.base import Message
from app.schemas.schedules import FixedScheduleCreate, FixedScheduleRead, FixedScheduleUpdate
from app.services.recurrence import SUPPORTED_RECURRENCE_RULES, normalize_recurrence_rule

router = APIRouter(prefix="/schedules/fixed", tags=["fixed-schedules"])

KST = timezone(timedelta(hours=9))


def _normalize_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(KST).replace(tzinfo=None)


def _validate_window(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at.")


def _validate_recurrence_rule(recurrence_rule: str | None, day_of_week: int | None = None) -> str | None:
    normalized = normalize_recurrence_rule(recurrence_rule)
    if recurrence_rule and normalized is None:
        supported = ", ".join(SUPPORTED_RECURRENCE_RULES)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported recurrence_rule. Use one of: {supported}.",
        )

    if normalized in ("weekly", "biweekly") and day_of_week is None:
        raise HTTPException(
            status_code=400,
            detail="weekly 및 biweekly 반복은 요일 선택이 필요합니다.",
        )

    return normalized


@router.post("", response_model=FixedScheduleRead, status_code=status.HTTP_201_CREATED)
def create_fixed_schedule(
    payload: FixedScheduleCreate,
    session: Session = Depends(get_db_session),
) -> FixedSchedule:
    require_user(session, payload.user_id)
    start_at = _normalize_local_datetime(payload.start_at)
    end_at = _normalize_local_datetime(payload.end_at)
    _validate_window(start_at, end_at)
    recurrence_rule = _validate_recurrence_rule(payload.recurrence_rule, payload.day_of_week)

    schedule = FixedSchedule(
        **payload.model_dump(exclude={"recurrence_rule", "start_at", "end_at"}),
        start_at=start_at,
        end_at=end_at,
        recurrence_rule=recurrence_rule,
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.get("", response_model=list[FixedScheduleRead])
def list_fixed_schedules(
    user_id: int = Query(...),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    session: Session = Depends(get_db_session),
) -> list[FixedSchedule]:
    require_user(session, user_id)

    conditions = [FixedSchedule.user_id == user_id]
    if start or end:
        non_recurring_conditions = [FixedSchedule.recurrence_rule.is_(None)]
        recurring_conditions = [FixedSchedule.recurrence_rule.is_not(None)]
        if start:
            non_recurring_conditions.append(FixedSchedule.end_at >= start)
        if end:
            non_recurring_conditions.append(FixedSchedule.start_at <= end)
            recurring_conditions.append(FixedSchedule.start_at <= end)
        conditions.append(
            or_(
                and_(*non_recurring_conditions),
                and_(*recurring_conditions),
            )
        )

    query = select(FixedSchedule).where(and_(*conditions)).order_by(FixedSchedule.start_at.asc())
    return session.scalars(query).all()


@router.patch("/{schedule_id}", response_model=FixedScheduleRead)
def update_fixed_schedule(
    schedule_id: int,
    payload: FixedScheduleUpdate,
    user_id: int = Query(...),
    session: Session = Depends(get_db_session),
) -> FixedSchedule:
    schedule = require_owned_resource(
        session,
        FixedSchedule,
        schedule_id,
        user_id,
        detail="Fixed schedule not found.",
    )

    updates = payload.model_dump(exclude_unset=True)
    if "start_at" in updates:
        updates["start_at"] = _normalize_local_datetime(updates["start_at"])
    if "end_at" in updates:
        updates["end_at"] = _normalize_local_datetime(updates["end_at"])
    next_start = updates.get("start_at", schedule.start_at)
    next_end = updates.get("end_at", schedule.end_at)
    _validate_window(next_start, next_end)
    next_day_of_week = updates.get("day_of_week", schedule.day_of_week)
    if "recurrence_rule" in updates:
        updates["recurrence_rule"] = _validate_recurrence_rule(updates["recurrence_rule"], next_day_of_week)
    else:
        _validate_recurrence_rule(schedule.recurrence_rule, next_day_of_week)

    for field, value in updates.items():
        setattr(schedule, field, value)

    session.commit()
    session.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", response_model=Message)
def delete_fixed_schedule(
    schedule_id: int,
    user_id: int = Query(...),
    session: Session = Depends(get_db_session),
) -> Message:
    schedule = require_owned_resource(
        session,
        FixedSchedule,
        schedule_id,
        user_id,
        detail="Fixed schedule not found.",
    )

    session.delete(schedule)
    session.commit()
    return Message(detail="Fixed schedule deleted.")
