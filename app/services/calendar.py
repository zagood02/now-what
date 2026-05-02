from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.ai_plan import AIPlanItem
from app.models.allocated_task import AllocatedTask
from app.models.fixed_schedule import FixedSchedule
from app.schemas.calendar import CalendarEventRead, CalendarResponse
from app.services.recurrence import expand_fixed_schedule


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
                        start_at=occurrence.start_at,
                        end_at=occurrence.end_at,
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
            select(AllocatedTask).where(
                AllocatedTask.user_id == user_id,
                AllocatedTask.scheduled_start < end,
                AllocatedTask.scheduled_end > start,
            ).order_by(AllocatedTask.scheduled_start.asc())
        ).all()
        for item in allocated_tasks:
            events.append(
                CalendarEventRead(
                    id=f"allocated-{item.id}",
                    source_type="allocated_task",
                    source_id=item.id,
                    title=item.title_snapshot,
                    description="Auto-allocated flexible task",
                    start_at=item.scheduled_start,
                    end_at=item.scheduled_end,
                    status="scheduled",
                    metadata_json={"flexible_task_id": item.flexible_task_id},
                )
            )

        plan_items = session.scalars(
            select(AIPlanItem).where(
                AIPlanItem.user_id == user_id,
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                AIPlanItem.scheduled_start < end,
                AIPlanItem.scheduled_end > start,
            ).order_by(AIPlanItem.scheduled_start.asc())
        ).all()
        for item in plan_items:
            events.append(
                CalendarEventRead(
                    id=f"plan-{item.id}",
                    source_type="ai_plan_item",
                    source_id=item.id,
                    title=item.title,
                    description=item.description,
                    start_at=item.scheduled_start,
                    end_at=item.scheduled_end,
                    status=item.status.value,
                    metadata_json={
                        "goal_id": item.goal_id,
                        "item_type": item.item_type,
                        "priority": item.priority,
                    },
                )
            )

        events.sort(key=lambda event: event.start_at)
        totals = {
            "fixed_schedule": sum(1 for event in events if event.source_type == "fixed_schedule"),
            "allocated_task": sum(1 for event in events if event.source_type == "allocated_task"),
            "ai_plan_item": sum(1 for event in events if event.source_type == "ai_plan_item"),
        }
        return CalendarResponse(user_id=user_id, start=start, end=end, events=events, totals=totals)
