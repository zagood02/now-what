from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.api.deps import require_owned_resource, require_user
from backend.db.session import get_db_session
from backend.models.flexible_task import FlexibleTask
from backend.schemas.base import Message
from backend.schemas.tasks import FlexibleTaskCreate, FlexibleTaskRead, FlexibleTaskUpdate

router = APIRouter(prefix="/tasks/flexible", tags=["flexible-tasks"])


def _validate_task_constraints(
    *,
    estimated_minutes: int,
    min_session_minutes: int,
    preferred_session_minutes: int,
    max_minutes_per_day: int,
) -> None:
    if preferred_session_minutes < min_session_minutes:
        raise HTTPException(
            status_code=400,
            detail="preferred_session_minutes must be greater than or equal to min_session_minutes.",
        )
    if max_minutes_per_day < min_session_minutes:
        raise HTTPException(
            status_code=400,
            detail="max_minutes_per_day must be greater than or equal to min_session_minutes.",
        )
    if estimated_minutes <= 0:
        raise HTTPException(status_code=400, detail="estimated_minutes must be greater than 0.")


@router.post("", response_model=FlexibleTaskRead, status_code=status.HTTP_201_CREATED)
def create_flexible_task(
    payload: FlexibleTaskCreate,
    session: Session = Depends(get_db_session),
) -> FlexibleTask:
    require_user(session, payload.user_id)
    _validate_task_constraints(
        estimated_minutes=payload.estimated_minutes,
        min_session_minutes=payload.min_session_minutes,
        preferred_session_minutes=payload.preferred_session_minutes,
        max_minutes_per_day=payload.max_minutes_per_day,
    )
    task = FlexibleTask(**payload.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[FlexibleTaskRead])
def list_flexible_tasks(
    user_id: int = Query(...),
    session: Session = Depends(get_db_session),
) -> list[FlexibleTask]:
    require_user(session, user_id)
    query = (
        select(FlexibleTask)
        .options(selectinload(FlexibleTask.allocations))
        .where(FlexibleTask.user_id == user_id)
        .order_by(FlexibleTask.priority.desc(), FlexibleTask.id.asc())
    )
    return session.scalars(query).all()


@router.patch("/{task_id}", response_model=FlexibleTaskRead)
def update_flexible_task(
    task_id: int,
    payload: FlexibleTaskUpdate,
    user_id: int = Query(...),
    session: Session = Depends(get_db_session),
) -> FlexibleTask:
    task = require_owned_resource(
        session,
        FlexibleTask,
        task_id,
        user_id,
        detail="Flexible task not found.",
    )

    updates = payload.model_dump(exclude_unset=True)
    _validate_task_constraints(
        estimated_minutes=updates.get("estimated_minutes", task.estimated_minutes),
        min_session_minutes=updates.get("min_session_minutes", task.min_session_minutes),
        preferred_session_minutes=updates.get(
            "preferred_session_minutes",
            task.preferred_session_minutes,
        ),
        max_minutes_per_day=updates.get("max_minutes_per_day", task.max_minutes_per_day),
    )

    for field, value in updates.items():
        setattr(task, field, value)

    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", response_model=Message)
def delete_flexible_task(
    task_id: int,
    user_id: int = Query(...),
    session: Session = Depends(get_db_session),
) -> Message:
    task = require_owned_resource(
        session,
        FlexibleTask,
        task_id,
        user_id,
        detail="Flexible task not found.",
    )

    session.delete(task)
    session.commit()
    return Message(detail="Flexible task deleted.")
