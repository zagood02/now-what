from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.ai_plan import AIPlanItem
from app.models.allocated_task import AllocatedTask
from app.models.enums import FlexibleTaskStatus, PlanItemStatus
from app.models.fixed_schedule import FixedSchedule
from app.models.flexible_task import FlexibleTask
from app.services.recurrence import expand_fixed_schedule


@dataclass
class TimeSlot:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class AllocationResult:
    allocated_tasks: list[AllocatedTask] = field(default_factory=list)
    scheduled_plan_items: list[AIPlanItem] = field(default_factory=list)
    unscheduled_task_ids: list[int] = field(default_factory=list)
    unscheduled_plan_item_ids: list[int] = field(default_factory=list)


class AllocationService:
    def allocate(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
        day_start: time,
        day_end: time,
        clear_existing: bool = False,
    ) -> AllocationResult:
        if clear_existing:
            affected_task_ids = session.scalars(
                select(AllocatedTask.flexible_task_id).where(
                    AllocatedTask.user_id == user_id,
                    AllocatedTask.scheduled_start < range_end,
                    AllocatedTask.scheduled_end > range_start,
                )
            ).all()

            session.query(AllocatedTask).filter(
                AllocatedTask.user_id == user_id,
                AllocatedTask.scheduled_start < range_end,
                AllocatedTask.scheduled_end > range_start,
            ).delete(synchronize_session=False)

            for task in session.scalars(select(FlexibleTask).where(FlexibleTask.id.in_(affected_task_ids))).all():
                if task.status in {FlexibleTaskStatus.completed, FlexibleTaskStatus.cancelled}:
                    continue
                has_remaining_allocations = bool(
                    session.scalar(
                        select(func.count(AllocatedTask.id)).where(AllocatedTask.flexible_task_id == task.id)
                    )
                )
                task.status = (
                    FlexibleTaskStatus.scheduled if has_remaining_allocations else FlexibleTaskStatus.pending
                )

            existing_items = session.scalars(
                select(AIPlanItem).where(
                    AIPlanItem.user_id == user_id,
                    AIPlanItem.scheduled_start.is_not(None),
                    AIPlanItem.scheduled_end.is_not(None),
                    AIPlanItem.scheduled_start < range_end,
                    AIPlanItem.scheduled_end > range_start,
                )
            ).all()
            for item in existing_items:
                item.scheduled_start = None
                item.scheduled_end = None
                if item.status != PlanItemStatus.completed:
                    item.status = PlanItemStatus.suggested

        busy_slots = self._load_busy_slots(session, user_id, range_start, range_end)
        free_slots = self._build_free_slots(range_start, range_end, day_start, day_end, busy_slots)

        task_result = self._allocate_flexible_tasks(session, user_id, range_start, range_end, free_slots)
        plan_result = self._allocate_plan_items(session, user_id, range_end, free_slots)
        return AllocationResult(
            allocated_tasks=task_result["allocated"],
            scheduled_plan_items=plan_result["scheduled"],
            unscheduled_task_ids=task_result["unscheduled"],
            unscheduled_plan_item_ids=plan_result["unscheduled"],
        )

    def _load_busy_slots(
        self,
        session: Session,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        fixed_schedules = session.scalars(
            select(FixedSchedule).where(
                FixedSchedule.user_id == user_id,
                or_(
                    and_(
                        FixedSchedule.recurrence_rule.is_(None),
                        FixedSchedule.start_at < range_end,
                        FixedSchedule.end_at > range_start,
                    ),
                    and_(
                        FixedSchedule.recurrence_rule.is_not(None),
                        FixedSchedule.start_at < range_end,
                    ),
                ),
            )
        ).all()
        allocated_tasks = session.scalars(
            select(AllocatedTask).where(
                AllocatedTask.user_id == user_id,
                AllocatedTask.scheduled_start < range_end,
                AllocatedTask.scheduled_end > range_start,
            )
        ).all()
        plan_items = session.scalars(
            select(AIPlanItem).where(
                AIPlanItem.user_id == user_id,
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                AIPlanItem.scheduled_start < range_end,
                AIPlanItem.scheduled_end > range_start,
            )
        ).all()

        intervals: list[tuple[datetime, datetime]] = []
        for item in fixed_schedules:
            intervals.extend(
                (occurrence.start_at, occurrence.end_at)
                for occurrence in expand_fixed_schedule(
                    item,
                    range_start=range_start,
                    range_end=range_end,
                )
            )
        intervals.extend((item.scheduled_start, item.scheduled_end) for item in allocated_tasks)
        intervals.extend(
            (item.scheduled_start, item.scheduled_end)
            for item in plan_items
            if item.scheduled_start and item.scheduled_end
        )
        return self._merge_intervals(intervals)

    def _build_free_slots(
        self,
        range_start: datetime,
        range_end: datetime,
        day_start: time,
        day_end: time,
        busy_slots: list[tuple[datetime, datetime]],
    ) -> list[TimeSlot]:
        slots: list[TimeSlot] = []
        current_day = range_start.date()
        last_day = range_end.date()
        tzinfo = range_start.tzinfo

        while current_day <= last_day:
            window_start = datetime.combine(current_day, day_start)
            window_end = datetime.combine(current_day, day_end)
            if tzinfo is not None:
                window_start = window_start.replace(tzinfo=tzinfo)
                window_end = window_end.replace(tzinfo=tzinfo)

            day_start_at = max(window_start, range_start)
            day_end_at = min(window_end, range_end)
            if day_end_at <= day_start_at:
                current_day += timedelta(days=1)
                continue

            pointer = day_start_at
            for busy_start, busy_end in busy_slots:
                if busy_end <= day_start_at or busy_start >= day_end_at:
                    continue
                clipped_start = max(busy_start, day_start_at)
                clipped_end = min(busy_end, day_end_at)
                if clipped_start > pointer:
                    slots.append(TimeSlot(start=pointer, end=clipped_start))
                if clipped_end > pointer:
                    pointer = clipped_end
            if pointer < day_end_at:
                slots.append(TimeSlot(start=pointer, end=day_end_at))
            current_day += timedelta(days=1)

        return [slot for slot in slots if slot.minutes > 0]

    def _minutes_available_before(self, slot: TimeSlot, deadline: datetime) -> int:
        effective_end = min(slot.end, deadline)
        if effective_end <= slot.start:
            return 0
        return int((effective_end - slot.start).total_seconds() // 60)

    def _allocate_flexible_tasks(
        self,
        session: Session,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
        free_slots: list[TimeSlot],
    ) -> dict[str, list]:
        ordering = [
            case((FlexibleTask.due_at.is_(None), 1), else_=0).asc(),
            FlexibleTask.due_at.asc(),
            FlexibleTask.priority.desc(),
            FlexibleTask.id.asc(),
        ]
        tasks = session.scalars(
            select(FlexibleTask).where(
                FlexibleTask.user_id == user_id,
                FlexibleTask.status.in_(
                    [
                        FlexibleTaskStatus.pending,
                        FlexibleTaskStatus.scheduled,
                        FlexibleTaskStatus.in_progress,
                    ]
                ),
                or_(FlexibleTask.due_at.is_(None), FlexibleTask.due_at >= range_start),
            ).order_by(*ordering)
        ).all()

        existing_minutes = {
            task_id: total_minutes
            for task_id, total_minutes in session.execute(
                select(
                    AllocatedTask.flexible_task_id,
                    func.coalesce(func.sum(AllocatedTask.duration_minutes), 0),
                )
                .where(AllocatedTask.user_id == user_id)
                .group_by(AllocatedTask.flexible_task_id)
            ).all()
        }

        allocated: list[AllocatedTask] = []
        unscheduled: list[int] = []
        minutes_by_task_day: dict[tuple[int, date], int] = {}

        for task in tasks:
            remaining = task.estimated_minutes - int(existing_minutes.get(task.id, 0))
            if remaining <= 0:
                continue

            task_deadline = min(task.due_at, range_end) if task.due_at else range_end
            task_was_allocated = False

            for slot in list(free_slots):
                if remaining <= 0:
                    break
                minutes_before_deadline = self._minutes_available_before(slot, task_deadline)
                if minutes_before_deadline <= 0:
                    continue

                day_key = slot.start.date()
                daily_used = minutes_by_task_day.get((task.id, day_key), 0)
                daily_remaining = max(task.max_minutes_per_day - daily_used, 0)
                if daily_remaining <= 0:
                    continue

                chunk_limit = min(
                    minutes_before_deadline,
                    remaining,
                    daily_remaining,
                    task.preferred_session_minutes,
                )
                if chunk_limit < task.min_session_minutes:
                    if remaining <= minutes_before_deadline and remaining <= daily_remaining:
                        chunk_limit = remaining
                    else:
                        continue

                record = AllocatedTask(
                    user_id=user_id,
                    flexible_task_id=task.id,
                    title_snapshot=task.title,
                    scheduled_start=slot.start,
                    scheduled_end=slot.start + timedelta(minutes=chunk_limit),
                    duration_minutes=chunk_limit,
                )
                session.add(record)
                session.flush()

                allocated.append(record)
                task_was_allocated = True
                remaining -= chunk_limit
                minutes_by_task_day[(task.id, day_key)] = daily_used + chunk_limit
                slot.start = record.scheduled_end

            free_slots[:] = [slot for slot in free_slots if slot.minutes > 0]
            if task_was_allocated and task.status in {FlexibleTaskStatus.pending, FlexibleTaskStatus.in_progress}:
                task.status = FlexibleTaskStatus.scheduled
            if remaining > 0:
                unscheduled.append(task.id)

        return {"allocated": allocated, "unscheduled": unscheduled}

    def _allocate_plan_items(
        self,
        session: Session,
        user_id: int,
        range_end: datetime,
        free_slots: list[TimeSlot],
    ) -> dict[str, list]:
        ordering = [
            case((AIPlanItem.target_date.is_(None), 1), else_=0).asc(),
            AIPlanItem.target_date.asc(),
            AIPlanItem.priority.desc(),
            AIPlanItem.id.asc(),
        ]
        items = session.scalars(
            select(AIPlanItem).where(
                AIPlanItem.user_id == user_id,
                AIPlanItem.is_schedulable.is_(True),
                AIPlanItem.scheduled_start.is_(None),
                AIPlanItem.status == PlanItemStatus.suggested,
            ).order_by(*ordering)
        ).all()

        scheduled: list[AIPlanItem] = []
        unscheduled: list[int] = []

        for item in items:
            duration = item.estimated_minutes or 60
            deadline = range_end
            if item.target_date:
                deadline = min(
                    range_end,
                    datetime.combine(item.target_date, time(23, 59)).replace(tzinfo=range_end.tzinfo),
                )

            slot_found = False
            for slot in free_slots:
                minutes_before_deadline = self._minutes_available_before(slot, deadline)
                if minutes_before_deadline < duration:
                    continue

                item.scheduled_start = slot.start
                item.scheduled_end = slot.start + timedelta(minutes=duration)
                item.status = PlanItemStatus.scheduled
                slot.start = item.scheduled_end
                scheduled.append(item)
                slot_found = True
                break

            free_slots[:] = [slot for slot in free_slots if slot.minutes > 0]
            if not slot_found:
                unscheduled.append(item.id)

        return {"scheduled": scheduled, "unscheduled": unscheduled}

    def _merge_intervals(self, intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
        if not intervals:
            return []

        ordered = sorted(intervals, key=lambda item: item[0])
        merged: list[tuple[datetime, datetime]] = [ordered[0]]
        for start, end in ordered[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged
