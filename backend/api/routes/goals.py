from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.api.deps import get_current_user, require_owned_resource
from backend.core.config import settings
from backend.core.timezone import normalize_to_kst_naive
from backend.db.session import get_db_session
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.enums import GoalStatus, PlanStatus
from backend.models.goal import Goal
from backend.models.user import User
from backend.schemas.base import Message
from backend.schemas.goals import AIPlanItemRead, AIPlanRead, GoalCreate, GoalDetailRead, GoalRead, GoalUpdate
from backend.schemas.schedules import AllocatedTaskRead
from backend.schemas.planning import (
    AllocateRequest,
    AllocateResponse,
    GoalCompleteRequest,
    GoalCompleteResponse,
    GoalIntakeRequest,
    GoalIntakeResponse,
)
from backend.services.allocation import AllocationConflictError, AllocationService
from backend.services.planning import PlanningService

router = APIRouter(tags=["goals"])
planning_service = PlanningService()
allocation_service = AllocationService()


def _parse_default_time(raw_value: str):
    return datetime.strptime(raw_value, "%H:%M").time()


@router.get("/goals", response_model=list[GoalRead])
def list_goals(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[Goal]:
    return session.scalars(
        select(Goal).where(Goal.user_id == current_user.id).order_by(Goal.created_at.desc())
    ).all()


@router.post("/goals", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Goal:
    goal = Goal(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        status=payload.status,
        target_date=payload.target_date,
        details_json=payload.details_json,
        answers_json=payload.answers_json,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.get("/goals/{goal_id}", response_model=GoalDetailRead)
def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Goal:
    goal = session.scalar(
        select(Goal)
        .options(selectinload(Goal.plans).selectinload(AIPlan.items))
        .where(Goal.id == goal_id, Goal.user_id == current_user.id)
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    goal.plans.sort(key=lambda item: item.created_at, reverse=True)
    return goal


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Goal:
    goal = require_owned_resource(session, Goal, goal_id, current_user.id, detail="Goal not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)

    session.commit()
    session.refresh(goal)
    return goal


@router.delete("/goals/{goal_id}", response_model=Message)
def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Message:
    goal = require_owned_resource(session, Goal, goal_id, current_user.id, detail="Goal not found.")
    session.delete(goal)
    session.commit()
    return Message(detail="Goal deleted.")


@router.post("/goals/{goal_id}/clear-schedule", response_model=Message)
def clear_goal_schedule(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Message:
    goal = require_owned_resource(session, Goal, goal_id, current_user.id, detail="Goal not found.")
    cleared_count = allocation_service.clear_goal_plan_item_schedules(
        session,
        user_id=current_user.id,
        goal_id=goal.id,
    )
    session.commit()
    return Message(detail=f"Cleared {cleared_count} scheduled plan item(s) for this goal.")


@router.post("/goals/{goal_id}/allocate", response_model=AllocateResponse)
def allocate_goal_schedule(
    goal_id: int,
    payload: AllocateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AllocateResponse:
    goal = require_owned_resource(session, Goal, goal_id, current_user.id, detail="Goal not found.")
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
                    goal_id=goal.id,
                    include_flexible_tasks=False,
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
        message="Goal allocation completed with automatic rescheduling.",
    )


@router.post("/goals/intake", response_model=GoalIntakeResponse)
def intake_goal(
    payload: GoalIntakeRequest,
    current_user: User = Depends(get_current_user),
) -> GoalIntakeResponse:
    return planning_service.parse_goal_input(payload)


@router.post("/goals/complete", response_model=GoalCompleteResponse, status_code=status.HTTP_201_CREATED)
def complete_goal(
    payload: GoalCompleteRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GoalCompleteResponse:
    parsed = planning_service.parse_goal_input(GoalIntakeRequest(text=payload.text, category=payload.category))
    try:
        goal = _create_goal_from_parsed(session, payload, parsed, user_id=current_user.id)
        plan, llm_mode = _generate_plan_for_goal(
            session,
            goal=goal,
            answers_json=payload.answers_json,
            replace_existing=payload.replace_existing,
        )
        session.commit()
        session.refresh(goal)
        session.refresh(plan)
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Goal plan generation failed.") from exc

    return GoalCompleteResponse(
        goal=GoalRead.model_validate(goal),
        plan=AIPlanRead.model_validate(plan),
        reasoning=parsed.reasoning,
        questions=parsed.questions,
        llm_mode=llm_mode,
    )


def _create_goal_from_parsed(
    session: Session,
    payload: GoalCompleteRequest,
    parsed: GoalIntakeResponse,
    *,
    user_id: int,
) -> Goal:
    merged_answers = {**parsed.goal.answers_json, **payload.answers_json}
    target_date = _parse_target_date(merged_answers.get("target_date"))
    goal = Goal(
        user_id=user_id,
        title=parsed.goal.title,
        description=parsed.goal.description,
        category=payload.category or parsed.goal.category,
        status=GoalStatus.draft,
        target_date=target_date,
        details_json=parsed.goal.details_json,
        answers_json=merged_answers,
    )
    session.add(goal)
    session.flush()
    return goal


def _generate_plan_for_goal(
    session: Session,
    *,
    goal: Goal,
    answers_json: dict,
    replace_existing: bool,
) -> tuple[AIPlan, str]:
    merged_answers = {**goal.answers_json, **answers_json}
    goal.answers_json = merged_answers
    if goal.status == GoalStatus.draft:
        goal.status = GoalStatus.active

    if replace_existing:
        existing_plans = session.scalars(
            select(AIPlan).where(
                AIPlan.user_id == goal.user_id,
                AIPlan.status == PlanStatus.active,
                AIPlan.goal_id == goal.id,
            )
        ).all()
        for plan in existing_plans:
            plan.status = PlanStatus.archived

    draft = planning_service.build_plan(goal, merged_answers)
    plan = AIPlan(
        user_id=goal.user_id,
        goal_id=goal.id,
        summary=draft.summary,
        strategy_json=draft.strategy_json,
        recommendations_json=draft.recommendations_json,
        raw_plan_json=draft.raw_plan_json,
        llm_mode=draft.llm_mode,
        status=PlanStatus.active,
    )
    session.add(plan)
    session.flush()

    plan_items: list[AIPlanItem] = []
    for item in draft.items:
        plan_item = AIPlanItem(
            ai_plan_id=plan.id,
            goal_id=goal.id,
            user_id=goal.user_id,
            title=item.title,
            description=item.description,
            item_type=item.item_type,
            estimated_minutes=item.estimated_minutes,
            priority=item.priority,
            target_date=item.target_date,
            is_schedulable=item.is_schedulable,
            metadata_json=item.metadata_json,
        )
        session.add(plan_item)
        plan_items.append(plan_item)

    session.flush()
    plan.items = plan_items
    return plan, draft.llm_mode


def _parse_target_date(value: object):
    from datetime import date

    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
