from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.core.timezone import normalize_optional_to_kst_naive, normalize_to_kst_naive
from backend.models.ai_plan import AIPlanItem
from backend.models.allocated_task import AllocatedTask
from backend.models.enums import FlexibleTaskStatus, PlanItemStatus
from backend.models.fixed_schedule import FixedSchedule
from backend.models.flexible_task import FlexibleTask
from backend.services.recurrence import expand_fixed_schedule


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


@dataclass
class AllocationCandidate:
    slot: TimeSlot
    start: datetime
    end: datetime
    duration_minutes: int
    score: tuple


class AllocationService:
    candidate_step_minutes = 30

    def allocate(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
        day_start: time,
        day_end: time,
        buffer_minutes: int = 30,
        max_auto_minutes_per_day: int | None = None,
        clear_existing: bool = True,
    ) -> AllocationResult:
        range_start = normalize_to_kst_naive(range_start)
        range_end = normalize_to_kst_naive(range_end)
        buffer_minutes = max(buffer_minutes, 0)
        if max_auto_minutes_per_day is not None and max_auto_minutes_per_day <= 0:
            max_auto_minutes_per_day = None

        if clear_existing:
            self._clear_auto_allocations(session, user_id, range_start, range_end)

        busy_slots = self._load_busy_slots(session, user_id, range_start, range_end)
        free_slots = self._build_free_slots(
            range_start,
            range_end,
            day_start,
            day_end,
            busy_slots,
            buffer_minutes=buffer_minutes,
        )
        auto_minutes_by_day, auto_minutes_by_bucket = self._load_existing_auto_minutes(
            session,
            user_id=user_id,
            range_start=range_start,
            range_end=range_end,
        )

        task_result = self._allocate_flexible_tasks(
            session,
            user_id,
            range_start,
            range_end,
            free_slots,
            buffer_minutes=buffer_minutes,
            max_auto_minutes_per_day=max_auto_minutes_per_day,
            auto_minutes_by_day=auto_minutes_by_day,
            auto_minutes_by_bucket=auto_minutes_by_bucket,
        )
        plan_result = self._allocate_plan_items(
            session,
            user_id,
            range_end,
            free_slots,
            buffer_minutes=buffer_minutes,
            max_auto_minutes_per_day=max_auto_minutes_per_day,
            auto_minutes_by_day=auto_minutes_by_day,
            auto_minutes_by_bucket=auto_minutes_by_bucket,
        )
        return AllocationResult(
            allocated_tasks=sorted(task_result["allocated"], key=lambda item: item.scheduled_start),
            scheduled_plan_items=sorted(plan_result["scheduled"], key=lambda item: item.scheduled_start),
            unscheduled_task_ids=task_result["unscheduled"],
            unscheduled_plan_item_ids=plan_result["unscheduled"],
        )

    def _clear_auto_allocations(
        self,
        session: Session,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> None:
        allocations = session.scalars(
            select(AllocatedTask)
            .join(FlexibleTask, AllocatedTask.flexible_task_id == FlexibleTask.id)
            .where(
                AllocatedTask.user_id == user_id,
                AllocatedTask.scheduled_start < range_end,
                AllocatedTask.scheduled_end > range_start,
                ~FlexibleTask.status.in_(
                    [FlexibleTaskStatus.completed, FlexibleTaskStatus.cancelled]
                ),
            )
        ).all()
        affected_task_ids = {allocation.flexible_task_id for allocation in allocations}
        for allocation in allocations:
            session.delete(allocation)
        session.flush()

        if affected_task_ids:
            for task in session.scalars(select(FlexibleTask).where(FlexibleTask.id.in_(affected_task_ids))).all():
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
                ~AIPlanItem.status.in_([PlanItemStatus.completed, PlanItemStatus.skipped]),
            )
        ).all()
        for item in existing_items:
            item.scheduled_start = None
            item.scheduled_end = None
            item.status = PlanItemStatus.suggested
        session.flush()

    def _load_busy_slots(
        self,
        session: Session,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        fixed_schedules = session.scalars(
            select(FixedSchedule).where(FixedSchedule.user_id == user_id)
        ).all()
        allocated_tasks = session.scalars(
            select(AllocatedTask).where(AllocatedTask.user_id == user_id)
        ).all()
        plan_items = session.scalars(
            select(AIPlanItem).where(
                AIPlanItem.user_id == user_id,
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
            )
        ).all()

        intervals: list[tuple[datetime, datetime]] = []
        for item in fixed_schedules:
            intervals.extend(
                (
                    normalize_to_kst_naive(occurrence.start_at),
                    normalize_to_kst_naive(occurrence.end_at),
                )
                for occurrence in expand_fixed_schedule(
                    item,
                    range_start=range_start,
                    range_end=range_end,
                )
            )
        intervals.extend(
            (
                normalize_to_kst_naive(item.scheduled_start),
                normalize_to_kst_naive(item.scheduled_end),
            )
            for item in allocated_tasks
        )
        intervals.extend(
            (
                normalize_to_kst_naive(item.scheduled_start),
                normalize_to_kst_naive(item.scheduled_end),
            )
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
        buffer_minutes: int = 0,
    ) -> list[TimeSlot]:
        range_start = normalize_to_kst_naive(range_start)
        range_end = normalize_to_kst_naive(range_end)
        buffer_delta = timedelta(minutes=max(buffer_minutes, 0))
        normalized_busy_slots: list[tuple[datetime, datetime]] = []
        for start, end in busy_slots:
            normalized_start = normalize_to_kst_naive(start) - buffer_delta
            normalized_end = normalize_to_kst_naive(end) + buffer_delta
            if normalized_end > normalized_start:
                normalized_busy_slots.append((normalized_start, normalized_end))
        busy_slots = self._merge_intervals(normalized_busy_slots)
        slots: list[TimeSlot] = []
        current_day = range_start.date()
        last_day = range_end.date()

        while current_day <= last_day:
            window_start = datetime.combine(current_day, day_start)
            window_end = datetime.combine(current_day, day_end)

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
        deadline = normalize_to_kst_naive(deadline)
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
        *,
        buffer_minutes: int,
        max_auto_minutes_per_day: int | None,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
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
        minutes_by_task_day = self._load_existing_task_daily_minutes(
            session,
            user_id=user_id,
            range_start=range_start,
            range_end=range_end,
        )

        for task in tasks:
            task.due_at = normalize_optional_to_kst_naive(task.due_at)
            if task.due_at and task.due_at < range_start:
                continue
            remaining = task.estimated_minutes - int(existing_minutes.get(task.id, 0))
            if remaining <= 0:
                continue

            task_deadline = min(task.due_at, range_end) if task.due_at else range_end
            task_was_allocated = False

            while remaining > 0:
                candidate = self._find_best_task_candidate(
                    free_slots,
                    task=task,
                    task_deadline=task_deadline,
                    remaining=remaining,
                    minutes_by_task_day=minutes_by_task_day,
                    auto_minutes_by_day=auto_minutes_by_day,
                    auto_minutes_by_bucket=auto_minutes_by_bucket,
                    max_auto_minutes_per_day=max_auto_minutes_per_day,
                )
                if candidate is None:
                    break

                record = AllocatedTask(
                    user_id=user_id,
                    flexible_task_id=task.id,
                    title_snapshot=task.title,
                    scheduled_start=candidate.start,
                    scheduled_end=candidate.end,
                    duration_minutes=candidate.duration_minutes,
                )
                session.add(record)
                session.flush()

                allocated.append(record)
                task_was_allocated = True
                remaining -= candidate.duration_minutes
                day_key = candidate.start.date()
                task_day_key = (task.id, day_key)
                minutes_by_task_day[task_day_key] = (
                    minutes_by_task_day.get(task_day_key, 0) + candidate.duration_minutes
                )
                self._add_auto_usage(
                    auto_minutes_by_day,
                    auto_minutes_by_bucket,
                    start_at=candidate.start,
                    end_at=candidate.end,
                )
                self._reserve_slot_time(
                    free_slots,
                    candidate.slot,
                    candidate.start,
                    candidate.end,
                    buffer_minutes=buffer_minutes,
                )

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
        *,
        buffer_minutes: int,
        max_auto_minutes_per_day: int | None,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
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
                    datetime.combine(item.target_date, time(23, 59)),
                )

            candidate = self._find_best_plan_item_candidate(
                free_slots,
                duration_minutes=duration,
                deadline=deadline,
                auto_minutes_by_day=auto_minutes_by_day,
                auto_minutes_by_bucket=auto_minutes_by_bucket,
                max_auto_minutes_per_day=max_auto_minutes_per_day,
            )
            if candidate:
                item.scheduled_start = candidate.start
                item.scheduled_end = candidate.end
                item.status = PlanItemStatus.scheduled
                scheduled.append(item)
                self._add_auto_usage(
                    auto_minutes_by_day,
                    auto_minutes_by_bucket,
                    start_at=candidate.start,
                    end_at=candidate.end,
                )
                self._reserve_slot_time(
                    free_slots,
                    candidate.slot,
                    candidate.start,
                    candidate.end,
                    buffer_minutes=buffer_minutes,
                )
            else:
                unscheduled.append(item.id)

        return {"scheduled": scheduled, "unscheduled": unscheduled}

    def _find_best_task_candidate(
        self,
        free_slots: list[TimeSlot],
        *,
        task: FlexibleTask,
        task_deadline: datetime,
        remaining: int,
        minutes_by_task_day: dict[tuple[int, date], int],
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        max_auto_minutes_per_day: int | None,
    ) -> AllocationCandidate | None:
        candidates: list[AllocationCandidate] = []
        minimum_duration = min(task.min_session_minutes, remaining)

        for slot in free_slots:
            effective_end = min(slot.end, task_deadline)
            if effective_end <= slot.start:
                continue

            for candidate_start in self._iter_candidate_starts(slot, effective_end, minimum_duration):
                minutes_before_deadline = int((effective_end - candidate_start).total_seconds() // 60)
                if minutes_before_deadline <= 0:
                    continue

                day_key = candidate_start.date()
                daily_used = minutes_by_task_day.get((task.id, day_key), 0)
                daily_remaining = max(task.max_minutes_per_day - daily_used, 0)
                auto_daily_remaining = self._auto_daily_remaining(
                    auto_minutes_by_day,
                    max_auto_minutes_per_day,
                    day_key,
                )
                if daily_remaining <= 0 or auto_daily_remaining <= 0:
                    continue

                chunk_limit = min(
                    minutes_before_deadline,
                    remaining,
                    daily_remaining,
                    auto_daily_remaining,
                    task.preferred_session_minutes,
                )
                if chunk_limit < task.min_session_minutes:
                    can_finish_remaining = (
                        remaining <= minutes_before_deadline
                        and remaining <= daily_remaining
                        and remaining <= auto_daily_remaining
                    )
                    if can_finish_remaining:
                        chunk_limit = remaining
                    else:
                        continue

                candidate_end = candidate_start + timedelta(minutes=chunk_limit)
                candidates.append(
                    AllocationCandidate(
                        slot=slot,
                        start=candidate_start,
                        end=candidate_end,
                        duration_minutes=chunk_limit,
                        score=self._candidate_score(
                            candidate_start,
                            chunk_limit,
                            auto_minutes_by_day,
                            auto_minutes_by_bucket,
                        ),
                    )
                )

        if not candidates:
            return None
        return min(candidates, key=lambda candidate: candidate.score)

    def _find_best_plan_item_candidate(
        self,
        free_slots: list[TimeSlot],
        *,
        duration_minutes: int,
        deadline: datetime,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        max_auto_minutes_per_day: int | None,
    ) -> AllocationCandidate | None:
        candidates: list[AllocationCandidate] = []

        for slot in free_slots:
            effective_end = min(slot.end, deadline)
            if effective_end <= slot.start:
                continue
            for candidate_start in self._iter_candidate_starts(slot, effective_end, duration_minutes):
                day_key = candidate_start.date()
                if self._auto_daily_remaining(
                    auto_minutes_by_day,
                    max_auto_minutes_per_day,
                    day_key,
                ) < duration_minutes:
                    continue
                candidate_end = candidate_start + timedelta(minutes=duration_minutes)
                candidates.append(
                    AllocationCandidate(
                        slot=slot,
                        start=candidate_start,
                        end=candidate_end,
                        duration_minutes=duration_minutes,
                        score=self._candidate_score(
                            candidate_start,
                            duration_minutes,
                            auto_minutes_by_day,
                            auto_minutes_by_bucket,
                        ),
                    )
                )

        if not candidates:
            return None
        return min(candidates, key=lambda candidate: candidate.score)

    def _iter_candidate_starts(
        self,
        slot: TimeSlot,
        effective_end: datetime,
        minimum_duration_minutes: int,
    ):
        latest_start = effective_end - timedelta(minutes=minimum_duration_minutes)
        if latest_start < slot.start:
            return

        step = timedelta(minutes=self.candidate_step_minutes)
        pointer = slot.start
        last_yielded: datetime | None = None
        while pointer <= latest_start:
            yield pointer
            last_yielded = pointer
            pointer += step
        if last_yielded != latest_start:
            yield latest_start

    def _candidate_score(
        self,
        start_at: datetime,
        duration_minutes: int,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
    ) -> tuple:
        day_key = start_at.date()
        bucket_key = (day_key, self._time_bucket(start_at))
        hour_value = start_at.hour + start_at.minute / 60
        center_penalty = int(abs(hour_value - 14) * 60)
        return (
            auto_minutes_by_day.get(day_key, 0),
            auto_minutes_by_bucket.get(bucket_key, 0),
            -duration_minutes,
            center_penalty,
            start_at,
        )

    def _auto_daily_remaining(
        self,
        auto_minutes_by_day: dict[date, int],
        max_auto_minutes_per_day: int | None,
        day_key: date,
    ) -> int:
        if max_auto_minutes_per_day is None:
            return 10**9
        return max(max_auto_minutes_per_day - auto_minutes_by_day.get(day_key, 0), 0)

    def _reserve_slot_time(
        self,
        free_slots: list[TimeSlot],
        slot: TimeSlot,
        start_at: datetime,
        end_at: datetime,
        *,
        buffer_minutes: int,
    ) -> None:
        buffer_delta = timedelta(minutes=max(buffer_minutes, 0))
        blocked_start = max(slot.start, start_at - buffer_delta)
        blocked_end = min(slot.end, end_at + buffer_delta)
        next_slots: list[TimeSlot] = []

        for current_slot in free_slots:
            if current_slot is not slot:
                next_slots.append(current_slot)
                continue
            if current_slot.start < blocked_start:
                next_slots.append(TimeSlot(start=current_slot.start, end=blocked_start))
            if blocked_end < current_slot.end:
                next_slots.append(TimeSlot(start=blocked_end, end=current_slot.end))

        free_slots[:] = sorted(
            [current_slot for current_slot in next_slots if current_slot.minutes > 0],
            key=lambda current_slot: current_slot.start,
        )

    def _load_existing_auto_minutes(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[dict[date, int], dict[tuple[date, str], int]]:
        day_window_start = datetime.combine(range_start.date(), time.min)
        day_window_end = datetime.combine(range_end.date() + timedelta(days=1), time.min)
        auto_minutes_by_day: dict[date, int] = {}
        auto_minutes_by_bucket: dict[tuple[date, str], int] = {}

        allocations = session.scalars(
            select(AllocatedTask).where(
                AllocatedTask.user_id == user_id,
                AllocatedTask.scheduled_start < day_window_end,
                AllocatedTask.scheduled_end > day_window_start,
            )
        ).all()
        for allocation in allocations:
            self._add_auto_usage(
                auto_minutes_by_day,
                auto_minutes_by_bucket,
                start_at=normalize_to_kst_naive(allocation.scheduled_start),
                end_at=normalize_to_kst_naive(allocation.scheduled_end),
            )

        plan_items = session.scalars(
            select(AIPlanItem).where(
                AIPlanItem.user_id == user_id,
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                AIPlanItem.scheduled_start < day_window_end,
                AIPlanItem.scheduled_end > day_window_start,
            )
        ).all()
        for item in plan_items:
            self._add_auto_usage(
                auto_minutes_by_day,
                auto_minutes_by_bucket,
                start_at=normalize_to_kst_naive(item.scheduled_start),
                end_at=normalize_to_kst_naive(item.scheduled_end),
            )

        return auto_minutes_by_day, auto_minutes_by_bucket

    def _add_auto_usage(
        self,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        if end_at <= start_at:
            return

        pointer = start_at
        while pointer < end_at:
            next_day = datetime.combine(pointer.date() + timedelta(days=1), time.min)
            chunk_end = min(end_at, next_day)
            minutes = int((chunk_end - pointer).total_seconds() // 60)
            day_key = pointer.date()
            bucket_key = (day_key, self._time_bucket(pointer))
            auto_minutes_by_day[day_key] = auto_minutes_by_day.get(day_key, 0) + minutes
            auto_minutes_by_bucket[bucket_key] = auto_minutes_by_bucket.get(bucket_key, 0) + minutes
            pointer = chunk_end

    def _time_bucket(self, start_at: datetime) -> str:
        if start_at.hour < 12:
            return "morning"
        if start_at.hour < 18:
            return "afternoon"
        return "evening"

    def _load_existing_task_daily_minutes(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> dict[tuple[int, date], int]:
        day_window_start = datetime.combine(range_start.date(), time.min)
        day_window_end = datetime.combine(range_end.date() + timedelta(days=1), time.min)
        allocations = session.scalars(
            select(AllocatedTask).where(
                AllocatedTask.user_id == user_id,
                AllocatedTask.scheduled_start < day_window_end,
                AllocatedTask.scheduled_end > day_window_start,
            )
        ).all()

        minutes_by_task_day: dict[tuple[int, date], int] = {}
        for allocation in allocations:
            self._add_interval_minutes_by_day(
                minutes_by_task_day,
                task_id=allocation.flexible_task_id,
                start_at=normalize_to_kst_naive(allocation.scheduled_start),
                end_at=normalize_to_kst_naive(allocation.scheduled_end),
            )
        return minutes_by_task_day

    def _add_interval_minutes_by_day(
        self,
        minutes_by_task_day: dict[tuple[int, date], int],
        *,
        task_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        if end_at <= start_at:
            return

        pointer = start_at
        while pointer < end_at:
            next_day = datetime.combine(pointer.date() + timedelta(days=1), time.min)
            chunk_end = min(end_at, next_day)
            minutes = int((chunk_end - pointer).total_seconds() // 60)
            day_key = (task_id, pointer.date())
            minutes_by_task_day[day_key] = minutes_by_task_day.get(day_key, 0) + minutes
            pointer = chunk_end

    def _merge_intervals(self, intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
        if not intervals:
            return []

        normalized_intervals: list[tuple[datetime, datetime]] = []
        for start, end in intervals:
            normalized_start = normalize_to_kst_naive(start)
            normalized_end = normalize_to_kst_naive(end)
            if normalized_end > normalized_start:
                normalized_intervals.append((normalized_start, normalized_end))

        ordered = sorted(normalized_intervals, key=lambda item: item[0])
        if not ordered:
            return []

        merged: list[tuple[datetime, datetime]] = [ordered[0]]
        for start, end in ordered[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged
