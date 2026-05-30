from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.core.timezone import normalize_to_kst_naive
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.allocated_task import AllocatedTask
from backend.models.enums import FlexibleTaskStatus, GoalStatus, PlanStatus
from backend.models.fixed_schedule import FixedSchedule
from backend.models.flexible_task import FlexibleTask
from backend.models.goal import Goal
from backend.models.variable_schedule import VariableSchedule
from backend.schemas.calendar import CalendarEventRead, CalendarResponse
from backend.services.recurrence import expand_fixed_schedule
from sqlalchemy.exc import ProgrammingError
import logging

logger = logging.getLogger(__name__)


class CalendarService:
    def build(self, session: Session, *, user_id: int, start: datetime, end: datetime) -> CalendarResponse:
        events: list[CalendarEventRead] = []

        fixed_schedules = session.scalars(
            select(FixedSchedule)
            .where(
                FixedSchedule.user_id == user_id,
                or_(
                    and_(
                        FixedSchedule.recurrence_rule.is_(None),
                        FixedSchedule.start_at < end,
                        FixedSchedule.end_at > start,
                    ),
                    and_(
                        FixedSchedule.recurrence_rule.is_not(None),
                        FixedSchedule.recurrence_rule != "",
                        FixedSchedule.start_at < end,
                    ),
                ),
            )
            .order_by(FixedSchedule.start_at.asc())
        ).all()
        for item in fixed_schedules:
            for occurrence in expand_fixed_schedule(item, range_start=start, range_end=end):
                try:
                    events.append(
                        CalendarEventRead(
                            id=f"fixed-{item.id}-{occurrence.occurrence_index}",
                            source_type="fixed_schedule",
                            source_id=item.id,
                            title=item.title,
                            description=item.description,
                            start_at=normalize_to_kst_naive(occurrence.start_at),
                            end_at=normalize_to_kst_naive(occurrence.end_at),
                            status="confirmed",
                            metadata_json={
                                "location": item.location,
                                "is_all_day": item.is_all_day,
                                "recurrence_rule": item.recurrence_rule,
                                "occurrence_index": occurrence.occurrence_index,
                            },
                        )
                    )
                except Exception:
                    logger.exception("Skipping invalid fixed_schedule event for schedule id %s", item.id)

        try:
            variable_schedules = session.scalars(
                select(VariableSchedule)
                .where(
                    VariableSchedule.user_id == user_id,
                    VariableSchedule.start_at < end,
                    VariableSchedule.end_at > start,
                )
                .order_by(VariableSchedule.start_at.asc())
            ).all()
        except ProgrammingError as exc:
            session.rollback()
            logger.warning(
                "Skipping variable_schedules query because the table does not exist: %s",
                exc,
            )
            variable_schedules = []

        for item in variable_schedules:
            try:
                events.append(
                    CalendarEventRead(
                        id=f"variable-{item.id}",
                        source_type="variable_schedule",
                        source_id=item.id,
                        title=item.title,
                        description=item.description,
                        start_at=normalize_to_kst_naive(item.start_at),
                        end_at=normalize_to_kst_naive(item.end_at),
                        status=item.status,
                        metadata_json={
                            "color_key": item.color_key,
                            "fatigue": item.fatigue,
                            "is_all_day": item.is_all_day,
                            **(item.details_json or {}),
                        },
                    )
                )
            except Exception:
                logger.exception("Skipping invalid variable_schedule event id %s", getattr(item, "id", None))

        allocated_tasks = session.scalars(
            select(AllocatedTask)
            .join(FlexibleTask, AllocatedTask.flexible_task_id == FlexibleTask.id)
            .where(
                AllocatedTask.user_id == user_id,
                FlexibleTask.status != FlexibleTaskStatus.cancelled,
                AllocatedTask.scheduled_start < end,
                AllocatedTask.scheduled_end > start,
            )
            .order_by(AllocatedTask.scheduled_start.asc())
        ).all()
        for item in allocated_tasks:
            try:
                events.append(
                    CalendarEventRead(
                        id=f"allocated-{item.id}",
                        source_type="allocated_task",
                        source_id=item.id,
                        title=item.title_snapshot,
                        description="Auto-allocated flexible task",
                        start_at=normalize_to_kst_naive(item.scheduled_start),
                        end_at=normalize_to_kst_naive(item.scheduled_end),
                        status="scheduled",
                        metadata_json={"flexible_task_id": item.flexible_task_id},
                    )
                )
            except Exception:
                logger.exception("Skipping invalid allocated_task event id %s", getattr(item, 'id', None))

        flexible_tasks = session.scalars(
            select(FlexibleTask)
            .where(
                FlexibleTask.user_id == user_id,
                FlexibleTask.status != FlexibleTaskStatus.cancelled,
            )
            .order_by(FlexibleTask.due_at.asc())
        ).all()

        for task in flexible_tasks:
            scheduled_start = task.details_json.get("scheduled_start")
            scheduled_end = task.details_json.get("scheduled_end")
            if not isinstance(scheduled_start, datetime) and isinstance(scheduled_start, str):
                try:
                    scheduled_start = datetime.fromisoformat(scheduled_start)
                except ValueError:
                    continue
            if not isinstance(scheduled_end, datetime) and isinstance(scheduled_end, str):
                try:
                    scheduled_end = datetime.fromisoformat(scheduled_end)
                except ValueError:
                    continue
            if scheduled_start is None or scheduled_end is None:
                continue

            scheduled_start = normalize_to_kst_naive(scheduled_start)
            scheduled_end = normalize_to_kst_naive(scheduled_end)

            if scheduled_end <= start or scheduled_start >= end:
                continue

            try:
                events.append(
                    CalendarEventRead(
                        id=f"flexible-{task.id}",
                        source_type="flexible_task",
                        source_id=task.id,
                        title=task.title,
                        description=task.description,
                        start_at=normalize_to_kst_naive(scheduled_start),
                        end_at=normalize_to_kst_naive(scheduled_end),
                        status=task.status.value,
                        metadata_json={"flexible_task_id": task.id},
                    )
                )
            except Exception:
                logger.exception("Skipping invalid flexible_task event id %s", getattr(task, 'id', None))

        plan_items = session.execute(
            select(AIPlanItem, Goal.title.label("goal_title"), AIPlan.id.label("ai_plan_id"))
            .join(AIPlan, AIPlanItem.ai_plan_id == AIPlan.id)
            .join(Goal, AIPlanItem.goal_id == Goal.id)
            .where(
                AIPlanItem.user_id == user_id,
                AIPlan.status == PlanStatus.active,
                Goal.status == GoalStatus.active,
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                AIPlanItem.scheduled_start < end,
                AIPlanItem.scheduled_end > start,
            ).order_by(AIPlanItem.scheduled_start.asc())
        ).all()
        for item, goal_title, ai_plan_id in plan_items:
            metadata = dict(item.metadata_json or {})
            metadata.update(
                {
                    "goal_id": item.goal_id,
                    "goal_title": goal_title,
                    "ai_plan_id": ai_plan_id,
                    "item_type": item.item_type,
                    "priority": item.priority,
                }
            )
            try:
                events.append(
                    CalendarEventRead(
                        id=f"plan-{item.id}",
                        source_type="ai_plan_item",
                        source_id=item.id,
                        title=item.title,
                        description=item.description,
                        start_at=normalize_to_kst_naive(item.scheduled_start),
                        end_at=normalize_to_kst_naive(item.scheduled_end),
                        status=item.status.value,
                        metadata_json=metadata,
                    )
                )
            except Exception:
                logger.exception("Skipping invalid ai_plan_item event id %s", getattr(item, 'id', None))

        events.sort(key=lambda event: event.start_at)
        totals = {
            "fixed_schedule": sum(1 for event in events if event.source_type == "fixed_schedule"),
            "variable_schedule": sum(1 for event in events if event.source_type == "variable_schedule"),
            "allocated_task": sum(1 for event in events if event.source_type == "allocated_task"),
            "ai_plan_item": sum(1 for event in events if event.source_type == "ai_plan_item"),
        }
        return CalendarResponse(user_id=user_id, start=start, end=end, events=events, totals=totals)
