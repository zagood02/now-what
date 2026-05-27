from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.api.deps import get_current_user, require_owned_resource
from backend.core.timezone import normalize_optional_to_kst_naive
from backend.db.session import get_db_session
from backend.models.allocated_task import AllocatedTask
from backend.models.enums import FlexibleTaskStatus
from backend.models.flexible_task import FlexibleTask
from backend.models.user import User
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


def _delete_task_allocations(session: Session, task: FlexibleTask) -> None:
    task.allocations.clear()
    session.flush()


@router.post("", response_model=FlexibleTaskRead, status_code=status.HTTP_201_CREATED)
def create_flexible_task(
    payload: FlexibleTaskCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> FlexibleTask:
    _validate_task_constraints(
        estimated_minutes=payload.estimated_minutes,
        min_session_minutes=payload.min_session_minutes,
        preferred_session_minutes=payload.preferred_session_minutes,
        max_minutes_per_day=payload.max_minutes_per_day,
    )
    data = payload.model_dump()
    data["due_at"] = normalize_optional_to_kst_naive(data.get("due_at"))
    task = FlexibleTask(**data, user_id=current_user.id)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[FlexibleTaskRead])
def list_flexible_tasks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[FlexibleTask]:
    query = (
        select(FlexibleTask)
        .options(selectinload(FlexibleTask.allocations))
        .where(FlexibleTask.user_id == current_user.id)
        .order_by(FlexibleTask.priority.desc(), FlexibleTask.id.asc())
    )
    return session.scalars(query).all()


@router.delete("/allocations/{allocation_id}", response_model=Message)
def delete_allocated_task(
    allocation_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Message:
    allocation = require_owned_resource(
        session,
        AllocatedTask,
        allocation_id,
        current_user.id,
        detail="Allocated task not found.",
    )
    task_id = allocation.flexible_task_id
    session.delete(allocation)
    session.flush()

    task = session.get(FlexibleTask, task_id)
    if task and task.status not in {FlexibleTaskStatus.completed, FlexibleTaskStatus.cancelled}:
        remaining_allocations = session.scalar(
            select(func.count(AllocatedTask.id)).where(AllocatedTask.flexible_task_id == task_id)
        )
        task.status = FlexibleTaskStatus.scheduled if remaining_allocations else FlexibleTaskStatus.pending

    session.commit()
    return Message(detail="Allocated task deleted.")


@router.get("/{task_id}", response_model=FlexibleTaskRead)
def get_flexible_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> FlexibleTask:
    task = session.scalar(
        select(FlexibleTask)
        .options(selectinload(FlexibleTask.allocations))
        .where(FlexibleTask.id == task_id, FlexibleTask.user_id == current_user.id)
    )
    if not task:
        raise HTTPException(status_code=404, detail="Flexible task not found.")
    return task


@router.patch("/{task_id}", response_model=FlexibleTaskRead)
def update_flexible_task(
    task_id: int,
    payload: FlexibleTaskUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> FlexibleTask:
    task = require_owned_resource(
        session,
        FlexibleTask,
        task_id,
        current_user.id,
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
        if field == "due_at":
            value = normalize_optional_to_kst_naive(value)
        setattr(task, field, value)

    if updates.get("status") in {FlexibleTaskStatus.pending, FlexibleTaskStatus.cancelled}:
        _delete_task_allocations(session, task)

    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", response_model=Message)
def delete_flexible_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Message:
    task = require_owned_resource(
        session,
        FlexibleTask,
        task_id,
        current_user.id,
        detail="Flexible task not found.",
    )

    session.delete(task)
    session.commit()
    return Message(detail="Flexible task deleted.")
