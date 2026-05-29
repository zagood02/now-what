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
from backend.schemas.calendar import CalendarEventRead, CalendarResponse
from backend.services.recurrence import expand_fixed_schedule


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

        events.sort(key=lambda event: event.start_at)
        totals = {
            "fixed_schedule": sum(1 for event in events if event.source_type == "fixed_schedule"),
            "allocated_task": sum(1 for event in events if event.source_type == "allocated_task"),
            "ai_plan_item": sum(1 for event in events if event.source_type == "ai_plan_item"),
        }
        return CalendarResponse(user_id=user_id, start=start, end=end, events=events, totals=totals)
