from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
import re
from threading import Lock, RLock
from typing import Any, ClassVar

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from backend.core.timezone import normalize_optional_to_kst_naive, normalize_to_kst_naive
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.allocated_task import AllocatedTask
from backend.models.enums import FlexibleTaskStatus, GoalStatus, PlanItemStatus, PlanStatus
from backend.models.fixed_schedule import FixedSchedule
from backend.models.flexible_task import FlexibleTask
from backend.models.goal import Goal
from backend.models.user import User
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


@dataclass(frozen=True)
class AllocationPreferenceWindow:
    start: time
    end: time
    days: frozenset[int] | None = None
    source: str = "answers"


@dataclass(frozen=True)
class AllocationPreferences:
    preferred_windows: tuple[AllocationPreferenceWindow, ...] = ()
    avoid_windows: tuple[AllocationPreferenceWindow, ...] = ()
    preferred_session_minutes: int | None = None
    max_session_minutes: int | None = None
    weekly_available_minutes: int | None = None
    max_weekday_items_per_day: int | None = None
    max_weekend_items_per_day: int | None = None
    max_weekday_minutes_per_day: int | None = None
    max_weekend_minutes_per_day: int | None = None
    week_anchor: date | None = None
    goal_target_date: date | None = None
    strict_preferred_windows: bool = False


class AllocationConflictError(RuntimeError):
    """Raised when schedule state changes while an allocation is being written."""


class AllocationService:
    candidate_step_minutes = 30
    max_plan_item_session_minutes = 120
    split_minutes_step = 5
    _user_lock_guard: ClassVar[Any] = Lock()
    _user_locks: ClassVar[dict[int, Any]] = {}

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
        goal_id: int | None = None,
        include_flexible_tasks: bool = True,
    ) -> AllocationResult:
        with self.allocation_transaction(session, user_id=user_id):
            return self._allocate_unlocked(
                session,
                user_id=user_id,
                range_start=range_start,
                range_end=range_end,
                day_start=day_start,
                day_end=day_end,
                buffer_minutes=buffer_minutes,
                max_auto_minutes_per_day=max_auto_minutes_per_day,
                clear_existing=clear_existing,
                goal_id=goal_id,
                include_flexible_tasks=include_flexible_tasks,
            )

    def _allocate_unlocked(
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
        goal_id: int | None = None,
        include_flexible_tasks: bool = True,
    ) -> AllocationResult:
        range_start = normalize_to_kst_naive(range_start)
        range_end = normalize_to_kst_naive(range_end)
        buffer_minutes = max(buffer_minutes, 0)
        if max_auto_minutes_per_day is not None and max_auto_minutes_per_day <= 0:
            max_auto_minutes_per_day = None

        if clear_existing:
            if goal_id is None:
                self._clear_auto_allocations(session, user_id, range_start, range_end)
            else:
                self.clear_goal_plan_item_schedules(
                    session,
                    user_id=user_id,
                    goal_id=goal_id,
                    range_start=range_start,
                    range_end=range_end,
                )

        busy_slots = self._load_busy_slots(session, user_id, range_start, range_end)
        free_slots = self._build_free_slots(
            range_start,
            range_end,
            day_start,
            day_end,
            busy_slots,
            buffer_minutes=buffer_minutes,
        )
        auto_minutes_by_day, auto_minutes_by_bucket, auto_count_by_day = self._load_existing_auto_usage(
            session,
            user_id=user_id,
            range_start=range_start,
            range_end=range_end,
        )

        task_result = {"allocated": [], "unscheduled": []}
        if include_flexible_tasks:
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
                auto_count_by_day=auto_count_by_day,
            )
        plan_result = self._allocate_plan_items(
            session,
            user_id,
            range_start,
            range_end,
            free_slots,
            goal_id=goal_id,
            buffer_minutes=buffer_minutes,
            max_auto_minutes_per_day=max_auto_minutes_per_day,
            auto_minutes_by_day=auto_minutes_by_day,
            auto_minutes_by_bucket=auto_minutes_by_bucket,
            auto_count_by_day=auto_count_by_day,
        )
        return AllocationResult(
            allocated_tasks=sorted(task_result["allocated"], key=lambda item: item.scheduled_start),
            scheduled_plan_items=sorted(plan_result["scheduled"], key=lambda item: item.scheduled_start),
            unscheduled_task_ids=task_result["unscheduled"],
            unscheduled_plan_item_ids=plan_result["unscheduled"],
        )

    @contextmanager
    def allocation_transaction(self, session: Session, *, user_id: int) -> Iterator[None]:
        with self._user_allocation_lock(user_id):
            self._lock_user_row(session, user_id)
            yield

    @contextmanager
    def _user_allocation_lock(self, user_id: int) -> Iterator[None]:
        with self._user_lock_guard:
            lock = self._user_locks.setdefault(user_id, RLock())
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def _lock_user_row(self, session: Session, user_id: int) -> None:
        session.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()

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
            self._active_plan_item_query(user_id)
            .where(
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
                        FixedSchedule.recurrence_rule != "",
                        FixedSchedule.start_at < range_end,
                    ),
                ),
            )
        ).all()
        allocated_tasks = session.scalars(
            select(AllocatedTask).join(FlexibleTask, AllocatedTask.flexible_task_id == FlexibleTask.id).where(
                AllocatedTask.user_id == user_id,
                FlexibleTask.status != FlexibleTaskStatus.cancelled,
                AllocatedTask.scheduled_start < range_end,
                AllocatedTask.scheduled_end > range_start,
            )
        ).all()
        plan_items = session.scalars(
            self._active_plan_item_query(user_id).where(
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                AIPlanItem.scheduled_start < range_end,
                AIPlanItem.scheduled_end > range_start,
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

    def clear_goal_plan_item_schedules(
        self,
        session: Session,
        *,
        user_id: int,
        goal_id: int,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> int:
        query = (
            self._active_plan_item_query(user_id)
            .where(
                AIPlanItem.goal_id == goal_id,
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                ~AIPlanItem.status.in_([PlanItemStatus.completed, PlanItemStatus.skipped]),
            )
        )
        if range_start is not None and range_end is not None:
            query = query.where(
                AIPlanItem.scheduled_start < normalize_to_kst_naive(range_end),
                AIPlanItem.scheduled_end > normalize_to_kst_naive(range_start),
            )

        items = session.scalars(query).all()
        for item in items:
            item.scheduled_start = None
            item.scheduled_end = None
            item.status = PlanItemStatus.suggested
        session.flush()
        return len(items)

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
        auto_count_by_day: dict[date, int],
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
                    auto_count_by_day=auto_count_by_day,
                    max_auto_minutes_per_day=max_auto_minutes_per_day,
                )
                if candidate is None:
                    break

                self._assert_candidate_is_still_free(
                    session,
                    user_id=user_id,
                    start_at=candidate.start,
                    end_at=candidate.end,
                )
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
                    auto_count_by_day=auto_count_by_day,
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
        range_start: datetime,
        range_end: datetime,
        free_slots: list[TimeSlot],
        *,
        goal_id: int | None,
        buffer_minutes: int,
        max_auto_minutes_per_day: int | None,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        auto_count_by_day: dict[date, int],
    ) -> dict[str, list]:
        ordering = [
            case((AIPlanItem.target_date.is_(None), 1), else_=0).asc(),
            AIPlanItem.target_date.asc(),
            AIPlanItem.priority.desc(),
            AIPlanItem.id.asc(),
        ]
        query = self._active_plan_item_query(user_id).where(
            AIPlanItem.is_schedulable.is_(True),
            AIPlanItem.scheduled_start.is_(None),
            AIPlanItem.status == PlanItemStatus.suggested,
        ).order_by(*ordering)
        if goal_id is not None:
            query = query.where(AIPlanItem.goal_id == goal_id)
        items = session.scalars(query).all()
        preferences_by_goal = self._load_goal_allocation_preferences(
            session,
            user_id=user_id,
            goal_ids={item.goal_id for item in items},
        )
        goal_minutes_by_week = self._load_existing_goal_plan_minutes_by_week(
            session,
            user_id=user_id,
            range_start=range_start,
            range_end=range_end,
            preferences_by_goal=preferences_by_goal,
        )

        scheduled: list[AIPlanItem] = []
        unscheduled: list[int] = []
        items = self._split_oversized_plan_items(session, items, preferences_by_goal=preferences_by_goal)
        session.flush()
        split_not_before_by_group: dict[tuple[Any, ...], datetime] = {}
        blocked_split_groups: set[tuple[Any, ...]] = set()

        for item in items:
            split_group_key = self._split_group_key(item)
            if split_group_key in blocked_split_groups:
                unscheduled.append(item.id)
                continue

            duration = self._round_minutes_to_step(item.estimated_minutes or 60)
            item.estimated_minutes = duration
            preferences = preferences_by_goal.get(item.goal_id, AllocationPreferences())
            deadline = range_end
            if preferences.goal_target_date:
                deadline = min(
                    range_end,
                    datetime.combine(preferences.goal_target_date, time(23, 59)),
                )

            candidate = self._find_best_plan_item_candidate(
                free_slots,
                duration_minutes=duration,
                deadline=deadline,
                target_date=item.target_date,
                auto_minutes_by_day=auto_minutes_by_day,
                auto_minutes_by_bucket=auto_minutes_by_bucket,
                auto_count_by_day=auto_count_by_day,
                max_auto_minutes_per_day=max_auto_minutes_per_day,
                preferences=preferences,
                goal_id=item.goal_id,
                goal_minutes_by_week=goal_minutes_by_week,
                not_before=split_not_before_by_group.get(split_group_key),
                prefer_earliest=split_group_key is not None,
            )
            if candidate:
                self._assert_candidate_is_still_free(
                    session,
                    user_id=user_id,
                    start_at=candidate.start,
                    end_at=candidate.end,
                )
                item.scheduled_start = candidate.start
                item.scheduled_end = candidate.end
                item.status = PlanItemStatus.scheduled
                scheduled.append(item)
                if split_group_key is not None:
                    split_not_before_by_group[split_group_key] = candidate.end
                self._add_auto_usage(
                    auto_minutes_by_day,
                    auto_minutes_by_bucket,
                    auto_count_by_day=auto_count_by_day,
                    start_at=candidate.start,
                    end_at=candidate.end,
                )
                self._add_goal_week_usage(
                    goal_minutes_by_week,
                    goal_id=item.goal_id,
                    start_at=candidate.start,
                    end_at=candidate.end,
                    preferences=preferences,
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
                if split_group_key is not None:
                    blocked_split_groups.add(split_group_key)

        return {"scheduled": scheduled, "unscheduled": unscheduled}

    def _split_oversized_plan_items(
        self,
        session: Session,
        items: list[AIPlanItem],
        *,
        preferences_by_goal: dict[int, AllocationPreferences] | None = None,
    ) -> list[AIPlanItem]:
        expanded: list[AIPlanItem] = []
        for item in items:
            duration = item.estimated_minutes or 60
            max_minutes = self._max_session_minutes_for_item(item, preferences_by_goal or {})
            if not item.is_schedulable or duration <= max_minutes:
                expanded.append(item)
                continue

            chunk_minutes = self._split_minutes(duration, max_minutes)
            original_title = item.title
            original_description = item.description
            original_metadata = self._as_dict(item.metadata_json)
            split_count = len(chunk_minutes)

            for index, minutes in enumerate(chunk_minutes):
                metadata = dict(original_metadata)
                metadata.update(
                    {
                        "split_from_ai_plan_item_id": item.id,
                        "split_from_estimated_minutes": duration,
                        "split_part": index + 1,
                        "split_count": split_count,
                    }
                )

                if index == 0:
                    item.title = self._split_item_title(original_title, index + 1, split_count)
                    item.description = self._split_item_description(original_description, index + 1, split_count)
                    item.estimated_minutes = minutes
                    item.metadata_json = metadata
                    expanded.append(item)
                    continue

                split_item = AIPlanItem(
                    ai_plan_id=item.ai_plan_id,
                    goal_id=item.goal_id,
                    user_id=item.user_id,
                    title=self._split_item_title(original_title, index + 1, split_count),
                    description=self._split_item_description(original_description, index + 1, split_count),
                    item_type=item.item_type,
                    estimated_minutes=minutes,
                    priority=item.priority,
                    target_date=item.target_date,
                    is_schedulable=item.is_schedulable,
                    status=PlanItemStatus.suggested,
                    metadata_json=metadata,
                )
                session.add(split_item)
                expanded.append(split_item)
        return expanded

    def _max_session_minutes_for_item(
        self,
        item: AIPlanItem,
        preferences_by_goal: dict[int, AllocationPreferences],
    ) -> int:
        preference_max = preferences_by_goal.get(item.goal_id, AllocationPreferences()).max_session_minutes
        if preference_max is None:
            return self.max_plan_item_session_minutes
        return max(min(preference_max, self.max_plan_item_session_minutes), self.candidate_step_minutes)

    def _split_minutes(self, total_minutes: int, max_minutes: int) -> list[int]:
        step = self.split_minutes_step
        total_units = self._round_minutes_to_step(total_minutes) // step
        max_units = max(int(max_minutes) // step, 1)
        chunk_count = (total_units + max_units - 1) // max_units
        base_units, extra_units = divmod(total_units, chunk_count)
        return [
            (base_units + (1 if index < extra_units else 0)) * step
            for index in range(chunk_count)
        ]

    def _round_minutes_to_step(self, minutes: int) -> int:
        step = self.split_minutes_step
        return max(step, ((int(minutes) + step - 1) // step) * step)

    def _split_item_title(self, title: str, part: int, count: int) -> str:
        suffix = f" ({part}/{count})"
        base_title = self._base_split_title(title)
        return f"{base_title[:200 - len(suffix)].rstrip()}{suffix}"

    def _split_item_description(self, description: str | None, part: int, count: int) -> str:
        return self._clean_split_description(description)

    def _split_group_key(self, item: AIPlanItem) -> tuple[Any, ...] | None:
        metadata = self._as_dict(item.metadata_json)
        split_part = metadata.get("split_part")
        split_count = metadata.get("split_count")
        try:
            split_count_value = int(split_count)
        except (TypeError, ValueError):
            return None
        if not split_part or split_count_value <= 1:
            return None

        source_item_id = metadata.get("split_from_ai_plan_item_id")
        if source_item_id is not None:
            return ("source_item", source_item_id)

        return (
            "generated_split",
            item.ai_plan_id,
            item.goal_id,
            item.item_type,
            item.target_date,
            metadata.get("split_from_estimated_minutes"),
            self._base_split_title(item.title),
        )

    def _base_split_title(self, title: str) -> str:
        return re.sub(r"(?:\s*\(\d+/\d+\))+$", "", title).strip()

    def _clean_split_description(self, description: str | None) -> str | None:
        if description is None:
            return None
        return re.sub(r"(?:\n\s*)*분할된 일정 \d+/\d+입니다\.\s*$", "", description).strip()

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
        auto_count_by_day: dict[date, int],
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
                            auto_count_by_day,
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
        target_date: date | None,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        auto_count_by_day: dict[date, int],
        max_auto_minutes_per_day: int | None,
        preferences: AllocationPreferences,
        goal_id: int,
        goal_minutes_by_week: dict[tuple[int, date], int],
        not_before: datetime | None = None,
        prefer_earliest: bool = False,
    ) -> AllocationCandidate | None:
        candidates: list[AllocationCandidate] = []
        if not_before is not None:
            not_before = normalize_to_kst_naive(not_before)

        for slot in free_slots:
            slot_start = max(slot.start, not_before) if not_before is not None else slot.start
            effective_end = min(slot.end, deadline)
            if effective_end <= slot_start:
                continue
            candidate_slot = TimeSlot(start=slot_start, end=slot.end)
            for candidate_start in self._iter_candidate_starts(candidate_slot, effective_end, duration_minutes):
                day_key = candidate_start.date()
                if self._auto_daily_remaining(
                    auto_minutes_by_day,
                    max_auto_minutes_per_day,
                    day_key,
                ) < duration_minutes:
                    continue
                candidate_end = candidate_start + timedelta(minutes=duration_minutes)
                if not self._matches_daily_preference_limits(
                    day_key,
                    duration_minutes,
                    auto_minutes_by_day,
                    auto_count_by_day,
                    preferences,
                ):
                    continue
                if self._violates_avoid_windows(candidate_start, candidate_end, preferences):
                    continue
                if preferences.strict_preferred_windows and not self._matches_preferred_window(
                    candidate_start,
                    candidate_end,
                    preferences,
                ):
                    continue
                if not self._goal_week_has_capacity(
                    goal_minutes_by_week,
                    goal_id=goal_id,
                    start_at=candidate_start,
                    end_at=candidate_end,
                    preferences=preferences,
                ):
                    continue
                candidates.append(
                    AllocationCandidate(
                        slot=slot,
                        start=candidate_start,
                        end=candidate_end,
                        duration_minutes=duration_minutes,
                        score=(
                            self._plan_item_split_candidate_score(
                                candidate_start,
                                duration_minutes,
                                auto_minutes_by_day,
                                auto_count_by_day,
                                target_date=target_date,
                                preferences=preferences,
                            )
                            if prefer_earliest
                            else self._plan_item_candidate_score(
                                candidate_start,
                                duration_minutes,
                                auto_minutes_by_day,
                                auto_minutes_by_bucket,
                                auto_count_by_day,
                                target_date=target_date,
                                preferences=preferences,
                            )
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
        auto_count_by_day: dict[date, int],
    ) -> tuple:
        day_key = start_at.date()
        bucket_key = (day_key, self._time_bucket(start_at))
        hour_value = start_at.hour + start_at.minute / 60
        center_penalty = int(abs(hour_value - 14) * 60)
        return (
            auto_minutes_by_day.get(day_key, 0),
            auto_count_by_day.get(day_key, 0),
            auto_minutes_by_bucket.get(bucket_key, 0),
            -duration_minutes,
            center_penalty,
            start_at,
        )

    def _plan_item_candidate_score(
        self,
        start_at: datetime,
        duration_minutes: int,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        auto_count_by_day: dict[date, int],
        *,
        target_date: date | None,
        preferences: AllocationPreferences | None = None,
    ) -> tuple:
        candidate_end = start_at + timedelta(minutes=duration_minutes)
        preference_penalty = self._preference_window_penalty(start_at, candidate_end, preferences)
        avoid_penalty = self._avoid_window_nearness_penalty(start_at, candidate_end, preferences)
        day_key = start_at.date()
        bucket_key = (day_key, self._time_bucket(start_at))
        hour_value = start_at.hour + start_at.minute / 60
        center_penalty = int(abs(hour_value - 14) * 60)
        target_penalty = 0 if target_date is None else abs((day_key - target_date).days)
        return (
            auto_minutes_by_day.get(day_key, 0),
            auto_count_by_day.get(day_key, 0),
            preference_penalty,
            avoid_penalty,
            target_penalty,
            auto_minutes_by_bucket.get(bucket_key, 0),
            -duration_minutes,
            center_penalty,
            start_at,
        )

    def _plan_item_split_candidate_score(
        self,
        start_at: datetime,
        duration_minutes: int,
        auto_minutes_by_day: dict[date, int],
        auto_count_by_day: dict[date, int],
        *,
        target_date: date | None,
        preferences: AllocationPreferences | None = None,
    ) -> tuple:
        candidate_end = start_at + timedelta(minutes=duration_minutes)
        day_key = start_at.date()
        target_penalty = 0 if target_date is None else abs((day_key - target_date).days)
        return (
            auto_minutes_by_day.get(day_key, 0),
            auto_count_by_day.get(day_key, 0),
            self._preference_window_penalty(start_at, candidate_end, preferences),
            self._avoid_window_nearness_penalty(start_at, candidate_end, preferences),
            target_penalty,
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

    def _matches_daily_preference_limits(
        self,
        day_key: date,
        duration_minutes: int,
        auto_minutes_by_day: dict[date, int],
        auto_count_by_day: dict[date, int],
        preferences: AllocationPreferences,
    ) -> bool:
        minutes_limit = self._daily_minutes_limit_for_day(day_key, preferences)
        if (
            minutes_limit is not None
            and auto_minutes_by_day.get(day_key, 0) + duration_minutes > minutes_limit
        ):
            return False

        count_limit = self._daily_count_limit_for_day(day_key, preferences)
        if count_limit is not None and auto_count_by_day.get(day_key, 0) + 1 > count_limit:
            return False
        return True

    def _daily_minutes_limit_for_day(
        self,
        day_key: date,
        preferences: AllocationPreferences,
    ) -> int | None:
        if day_key.weekday() < 5:
            return preferences.max_weekday_minutes_per_day
        return preferences.max_weekend_minutes_per_day

    def _daily_count_limit_for_day(
        self,
        day_key: date,
        preferences: AllocationPreferences,
    ) -> int | None:
        if day_key.weekday() < 5:
            return preferences.max_weekday_items_per_day
        return preferences.max_weekend_items_per_day

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

    def _assert_candidate_is_still_free(
        self,
        session: Session,
        *,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        conflicts = self._load_busy_slots(session, user_id, start_at, end_at)
        if any(start_at < busy_end and end_at > busy_start for busy_start, busy_end in conflicts):
            raise AllocationConflictError("Schedule changed during allocation. Please retry.")

    def _load_existing_auto_minutes(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[dict[date, int], dict[tuple[date, str], int]]:
        auto_minutes_by_day, auto_minutes_by_bucket, _ = self._load_existing_auto_usage(
            session,
            user_id=user_id,
            range_start=range_start,
            range_end=range_end,
        )
        return auto_minutes_by_day, auto_minutes_by_bucket

    def _load_existing_auto_usage(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[dict[date, int], dict[tuple[date, str], int], dict[date, int]]:
        day_window_start = datetime.combine(range_start.date(), time.min)
        day_window_end = datetime.combine(range_end.date() + timedelta(days=1), time.min)
        auto_minutes_by_day: dict[date, int] = {}
        auto_minutes_by_bucket: dict[tuple[date, str], int] = {}
        auto_count_by_day: dict[date, int] = {}

        allocations = session.scalars(
            select(AllocatedTask).join(FlexibleTask, AllocatedTask.flexible_task_id == FlexibleTask.id).where(
                AllocatedTask.user_id == user_id,
                FlexibleTask.status != FlexibleTaskStatus.cancelled,
                AllocatedTask.scheduled_start < day_window_end,
                AllocatedTask.scheduled_end > day_window_start,
            )
        ).all()
        for allocation in allocations:
            self._add_auto_usage(
                auto_minutes_by_day,
                auto_minutes_by_bucket,
                auto_count_by_day=auto_count_by_day,
                start_at=normalize_to_kst_naive(allocation.scheduled_start),
                end_at=normalize_to_kst_naive(allocation.scheduled_end),
            )

        plan_items = session.scalars(
            self._active_plan_item_query(user_id).where(
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
                auto_count_by_day=auto_count_by_day,
                start_at=normalize_to_kst_naive(item.scheduled_start),
                end_at=normalize_to_kst_naive(item.scheduled_end),
            )

        return auto_minutes_by_day, auto_minutes_by_bucket, auto_count_by_day

    def _add_auto_usage(
        self,
        auto_minutes_by_day: dict[date, int],
        auto_minutes_by_bucket: dict[tuple[date, str], int],
        *,
        auto_count_by_day: dict[date, int] | None = None,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        if end_at <= start_at:
            return

        pointer = start_at
        touched_days: set[date] = set()
        while pointer < end_at:
            next_day = datetime.combine(pointer.date() + timedelta(days=1), time.min)
            chunk_end = min(end_at, next_day)
            minutes = int((chunk_end - pointer).total_seconds() // 60)
            day_key = pointer.date()
            touched_days.add(day_key)
            bucket_key = (day_key, self._time_bucket(pointer))
            auto_minutes_by_day[day_key] = auto_minutes_by_day.get(day_key, 0) + minutes
            auto_minutes_by_bucket[bucket_key] = auto_minutes_by_bucket.get(bucket_key, 0) + minutes
            pointer = chunk_end
        if auto_count_by_day is not None:
            for day_key in touched_days:
                auto_count_by_day[day_key] = auto_count_by_day.get(day_key, 0) + 1

    def _load_goal_allocation_preferences(
        self,
        session: Session,
        *,
        user_id: int,
        goal_ids: set[int],
    ) -> dict[int, AllocationPreferences]:
        if not goal_ids:
            return {}

        goals = session.scalars(
            select(Goal).where(Goal.user_id == user_id, Goal.id.in_(goal_ids))
        ).all()
        preferences_by_goal: dict[int, AllocationPreferences] = {}
        for goal in goals:
            preferences = self._allocation_preferences_from_answers(goal.answers_json)
            preferences_by_goal[goal.id] = replace(
                preferences,
                week_anchor=(
                    normalize_to_kst_naive(goal.created_at).date()
                    if goal.created_at
                    else None
                ),
                goal_target_date=goal.target_date,
            )
        return preferences_by_goal

    def _allocation_preferences_from_answers(self, answers: Any) -> AllocationPreferences:
        source = self._as_dict(answers)
        nested = self._as_dict(source.get("allocation_preferences"))
        data = {**source, **nested} if nested else source

        preferred_session_minutes, max_session_minutes = self._session_minutes_from_answers(data)
        weekly_available_minutes = self._weekly_available_minutes_from_answers(data)
        preferred_windows = self._windows_from_answers(
            data,
            structured_keys=("preferred_windows", "preferred_time_windows"),
            text_keys=("preferred_work_times", "preferred_times", "preferred_time"),
            source="preferred",
        )
        avoid_windows = self._windows_from_answers(
            data,
            structured_keys=("avoid_windows", "unavailable_windows", "blocked_windows"),
            text_keys=("unavailable_times", "avoid_times", "avoid_time"),
            source="avoid",
        )
        return AllocationPreferences(
            preferred_windows=tuple(preferred_windows),
            avoid_windows=tuple(avoid_windows),
            preferred_session_minutes=preferred_session_minutes,
            max_session_minutes=max_session_minutes,
            weekly_available_minutes=weekly_available_minutes,
            max_weekday_items_per_day=self._positive_int_from_keys(
                data,
                (
                    "max_weekday_items_per_day",
                    "weekday_max_items_per_day",
                    "max_weekday_items",
                ),
            ),
            max_weekend_items_per_day=self._positive_int_from_keys(
                data,
                (
                    "max_weekend_items_per_day",
                    "weekend_max_items_per_day",
                    "max_weekend_items",
                ),
            ),
            max_weekday_minutes_per_day=self._daily_limit_minutes_from_keys(
                data,
                minute_keys=(
                    "max_weekday_minutes_per_day",
                    "weekday_max_minutes_per_day",
                    "max_weekday_minutes",
                ),
                hour_keys=(
                    "max_weekday_hours_per_day",
                    "weekday_max_hours_per_day",
                    "max_weekday_hours",
                ),
            ),
            max_weekend_minutes_per_day=self._daily_limit_minutes_from_keys(
                data,
                minute_keys=(
                    "max_weekend_minutes_per_day",
                    "weekend_max_minutes_per_day",
                    "max_weekend_minutes",
                ),
                hour_keys=(
                    "max_weekend_hours_per_day",
                    "weekend_max_hours_per_day",
                    "max_weekend_hours",
                ),
            ),
            strict_preferred_windows=self._bool_value(data.get("strict_preferred_windows")),
        )

    def _windows_from_answers(
        self,
        answers: dict[str, Any],
        *,
        structured_keys: tuple[str, ...],
        text_keys: tuple[str, ...],
        source: str,
    ) -> list[AllocationPreferenceWindow]:
        windows: list[AllocationPreferenceWindow] = []
        for key in structured_keys:
            windows.extend(self._windows_from_structured(answers.get(key)))
        for key in text_keys:
            windows.extend(self._windows_from_text(answers.get(key), source=source))
        return windows

    def _windows_from_structured(self, raw_windows: Any) -> list[AllocationPreferenceWindow]:
        if not isinstance(raw_windows, list):
            return []

        windows: list[AllocationPreferenceWindow] = []
        for raw_window in raw_windows:
            data = self._as_dict(raw_window)
            if not data:
                continue
            start = self._parse_time_value(data.get("start") or data.get("start_time"))
            end = self._parse_time_value(data.get("end") or data.get("end_time"))
            if start is None or end is None or end == start:
                continue
            windows.extend(
                self._expand_preference_window(
                    start,
                    end,
                    days=self._parse_days_value(data.get("days") or data.get("day") or data.get("day_of_week")),
                    source="structured",
                )
            )
        return windows

    def _windows_from_text(self, raw_text: Any, *, source: str) -> list[AllocationPreferenceWindow]:
        if raw_text is None:
            return []
        text = self._clean_text(str(raw_text))
        if not text:
            return []

        chunks = [chunk.strip() for chunk in re.split(r"[,;/\n]| 그리고 | 또는 ", text) if chunk.strip()]
        if not chunks:
            chunks = [text]

        windows: list[AllocationPreferenceWindow] = []
        for chunk in chunks:
            days = self._parse_days_from_text(chunk)
            time_ranges = self._parse_time_ranges_from_text(chunk)
            if not time_ranges:
                time_ranges = self._keyword_time_ranges(chunk)
            for start, end in time_ranges:
                windows.extend(self._expand_preference_window(start, end, days=days, source=source))
        return windows

    def _expand_preference_window(
        self,
        start: time,
        end: time,
        *,
        days: frozenset[int] | None,
        source: str,
    ) -> list[AllocationPreferenceWindow]:
        if end > start:
            return [AllocationPreferenceWindow(start=start, end=end, days=days, source=source)]
        if end == start:
            return []

        next_days = None if days is None else frozenset((day + 1) % 7 for day in days)
        windows = [AllocationPreferenceWindow(start=start, end=time(23, 59), days=days, source=source)]
        if end > time.min:
            windows.append(AllocationPreferenceWindow(start=time.min, end=end, days=next_days, source=source))
        return windows

    def _parse_days_value(self, value: Any) -> frozenset[int] | None:
        if value is None:
            return None
        if isinstance(value, int):
            return frozenset({value}) if 0 <= value <= 6 else None
        if isinstance(value, str):
            return self._parse_days_from_text(value)
        if isinstance(value, list):
            days: set[int] = set()
            for item in value:
                parsed = self._parse_days_value(item)
                if parsed is None:
                    continue
                days.update(parsed)
            return frozenset(days) if days else None
        return None

    def _parse_days_from_text(self, text: str) -> frozenset[int] | None:
        normalized = self._clean_text(text).lower()
        if not normalized:
            return None

        days: set[int] = set()
        if any(token in normalized for token in ("평일", "weekday", "weekdays")):
            days.update({0, 1, 2, 3, 4})
        if any(token in normalized for token in ("주말", "weekend", "weekends")):
            days.update({5, 6})
        if any(token in normalized for token in ("매일", "daily", "every day")):
            return None

        day_tokens = {
            0: (r"월요일|(?<![가-힣])월(?![가-힣])", r"\bmonday\b|\bmon\b"),
            1: (r"화요일|(?<![가-힣])화(?![가-힣])", r"\btuesday\b|\btue\b"),
            2: (r"수요일|(?<![가-힣])수(?![가-힣])", r"\bwednesday\b|\bwed\b"),
            3: (r"목요일|(?<![가-힣])목(?![가-힣])", r"\bthursday\b|\bthu\b"),
            4: (r"금요일|(?<![가-힣])금(?![가-힣])", r"\bfriday\b|\bfri\b"),
            5: (r"토요일|(?<![가-힣])토(?![가-힣])", r"\bsaturday\b|\bsat\b"),
            6: (r"일요일", r"\bsunday\b|\bsun\b"),
        }
        for day_index, patterns in day_tokens.items():
            if any(re.search(pattern, normalized) for pattern in patterns):
                days.add(day_index)
        return frozenset(days) if days else None

    def _parse_time_ranges_from_text(self, text: str) -> list[tuple[time, time]]:
        ranges: list[tuple[time, time]] = []
        for match in re.finditer(
            r"(?<!\d)(\d{1,2})(?::(\d{2}))?\s*(?:시|h)?\s*(?:-|~|부터|에서)\s*(\d{1,2})(?::(\d{2}))?\s*(?:시|h)?",
            text,
        ):
            start_hour = int(match.group(1))
            start_minute = int(match.group(2) or 0)
            end_hour = int(match.group(3))
            end_minute = int(match.group(4) or 0)
            start_hour, end_hour = self._apply_period_hint(text, start_hour, end_hour)
            start = self._safe_time(start_hour, start_minute)
            end = self._safe_time(end_hour, end_minute)
            if start is not None and end is not None and end != start:
                ranges.append((start, end))
        return ranges

    def _keyword_time_ranges(self, text: str) -> list[tuple[time, time]]:
        lowered = text.lower()
        if "점심" in lowered or "lunch" in lowered:
            return [(time(12), time(13))]
        if "오전" in lowered or "아침" in lowered or "morning" in lowered:
            return [(time(9), time(12))]
        if "오후" in lowered or "afternoon" in lowered:
            return [(time(13), time(18))]
        if "저녁" in lowered or "evening" in lowered:
            return [(time(18), time(22))]
        if "늦은 밤" in lowered or "late night" in lowered:
            return [(time(22), time(23, 59))]
        if "밤" in lowered or "night" in lowered:
            return [(time(20), time(23))]
        return []

    def _apply_period_hint(self, text: str, start_hour: int, end_hour: int) -> tuple[int, int]:
        lowered = text.lower()
        pm_hint = any(token in lowered for token in ("오후", "저녁", "밤", "pm", "evening", "night"))
        morning_hint = any(token in lowered for token in ("오전", "아침", "am", "morning"))
        if pm_hint:
            if start_hour < 12:
                start_hour += 12
            if end_hour < 12:
                end_hour += 12
        elif not morning_hint and start_hour <= 7 and end_hour <= 12:
            start_hour += 12
            end_hour += 12
        return start_hour, end_hour

    def _parse_time_value(self, value: Any) -> time | None:
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            match = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*", value)
            if not match:
                return None
            return self._safe_time(int(match.group(1)), int(match.group(2) or 0))
        return None

    def _safe_time(self, hour: int, minute: int) -> time | None:
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return None
        return time(hour, minute)

    def _session_minutes_from_answers(self, answers: dict[str, Any]) -> tuple[int | None, int | None]:
        preferred = self._minutes_value(answers.get("preferred_session_minutes"))
        maximum = self._minutes_value(answers.get("max_session_minutes"))
        session_preference = answers.get("session_preference")
        if isinstance(session_preference, str):
            numbers = [int(value) for value in re.findall(r"\d+", session_preference)]
            if "시간" in session_preference or "hour" in session_preference.lower():
                numbers = [value * 60 if value <= 12 else value for value in numbers]
            if numbers and preferred is None:
                preferred = min(numbers)
            if numbers and maximum is None:
                maximum = max(numbers)

        preferred = self._bounded_minutes(preferred)
        maximum = self._bounded_minutes(maximum)
        if maximum is None and preferred is not None:
            maximum = preferred
        if preferred is not None and maximum is not None and preferred > maximum:
            preferred = maximum
        return preferred, maximum

    def _weekly_available_minutes_from_answers(self, answers: dict[str, Any]) -> int | None:
        explicit_minutes = self._minutes_value(answers.get("weekly_available_minutes"))
        if explicit_minutes is not None:
            return self._bounded_weekly_minutes(explicit_minutes)

        hours = self._number_value(answers.get("weekly_available_hours") or answers.get("weekly_hours"))
        if hours is None:
            daily_minutes = self._minutes_value(answers.get("daily_available_minutes"))
            active_days = self._number_value(answers.get("study_days_per_week") or answers.get("active_days_per_week"))
            if daily_minutes is not None and active_days is not None:
                return self._bounded_weekly_minutes(int(daily_minutes * active_days))
            return None
        return self._bounded_weekly_minutes(int(hours * 60))

    def _positive_int_from_keys(self, answers: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        for key in keys:
            value = self._number_value(answers.get(key))
            if value is not None and value > 0:
                return max(int(value), 1)
        return None

    def _daily_limit_minutes_from_keys(
        self,
        answers: dict[str, Any],
        *,
        minute_keys: tuple[str, ...],
        hour_keys: tuple[str, ...],
    ) -> int | None:
        for key in minute_keys:
            value = self._minutes_value(answers.get(key))
            if value is not None:
                return self._bounded_daily_minutes(value)
        for key in hour_keys:
            value = self._number_value(answers.get(key))
            if value is not None:
                return self._bounded_daily_minutes(int(value * 60))
        return None

    def _minutes_value(self, value: Any) -> int | None:
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return None
        number = float(match.group(1))
        if "시간" in text or "hour" in text.lower() or re.search(r"\bhr?s?\b", text, flags=re.IGNORECASE):
            return int(number * 60)
        return int(number)

    def _number_value(self, value: Any) -> float | None:
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        if isinstance(value, str):
            match = re.search(r"(\d+(?:\.\d+)?)", value)
            if match:
                return float(match.group(1))
        return None

    def _bounded_minutes(self, value: int | None) -> int | None:
        if value is None:
            return None
        return max(min(value, self.max_plan_item_session_minutes), self.candidate_step_minutes)

    def _bounded_weekly_minutes(self, value: int | None) -> int | None:
        if value is None or value <= 0:
            return None
        return min(value, 7 * 24 * 60)

    def _bounded_daily_minutes(self, value: int | None) -> int | None:
        if value is None or value <= 0:
            return None
        return min(value, 24 * 60)

    def _bool_value(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized in {"1", "true", "yes", "y", "on", "strict"}
        return False

    def _preference_window_penalty(
        self,
        start_at: datetime,
        end_at: datetime,
        preferences: AllocationPreferences | None,
    ) -> int:
        if preferences is None or not preferences.preferred_windows:
            return 0
        distances = [
            self._preferred_window_distance_minutes(window, start_at, end_at)
            for window in preferences.preferred_windows
            if self._window_applies_to_day(window, start_at.date())
        ]
        if not distances:
            return 24 * 60
        return min(distances)

    def _avoid_window_nearness_penalty(
        self,
        start_at: datetime,
        end_at: datetime,
        preferences: AllocationPreferences | None,
    ) -> int:
        if preferences is None or not preferences.avoid_windows:
            return 0
        distances = [
            self._window_distance_minutes(window, start_at, end_at)
            for window in preferences.avoid_windows
            if self._window_applies_to_day(window, start_at.date())
        ]
        if not distances:
            return 0
        return max(0, (2 * 60) - min(distances))

    def _matches_preferred_window(
        self,
        start_at: datetime,
        end_at: datetime,
        preferences: AllocationPreferences,
    ) -> bool:
        if not preferences.preferred_windows:
            return True
        return any(
            self._window_contains(window, start_at, end_at)
            for window in preferences.preferred_windows
        )

    def _violates_avoid_windows(
        self,
        start_at: datetime,
        end_at: datetime,
        preferences: AllocationPreferences,
    ) -> bool:
        return any(
            self._window_overlaps(window, start_at, end_at)
            for window in preferences.avoid_windows
        )

    def _window_contains(self, window: AllocationPreferenceWindow, start_at: datetime, end_at: datetime) -> bool:
        if not self._window_applies_to_day(window, start_at.date()):
            return False
        return start_at.time() >= window.start and end_at.time() <= window.end

    def _window_overlaps(self, window: AllocationPreferenceWindow, start_at: datetime, end_at: datetime) -> bool:
        if not self._window_applies_to_day(window, start_at.date()):
            return False
        return start_at.time() < window.end and end_at.time() > window.start

    def _window_applies_to_day(self, window: AllocationPreferenceWindow, day: date) -> bool:
        return window.days is None or day.weekday() in window.days

    def _window_distance_minutes(
        self,
        window: AllocationPreferenceWindow,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        window_start = datetime.combine(start_at.date(), window.start)
        window_end = datetime.combine(start_at.date(), window.end)
        if start_at >= window_start and end_at <= window_end:
            return 0
        if end_at <= window_start:
            return int((window_start - end_at).total_seconds() // 60)
        if start_at >= window_end:
            return int((start_at - window_end).total_seconds() // 60)
        return 0

    def _preferred_window_distance_minutes(
        self,
        window: AllocationPreferenceWindow,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        window_start = datetime.combine(start_at.date(), window.start)
        window_end = datetime.combine(start_at.date(), window.end)
        if start_at >= window_start and end_at <= window_end:
            return 0
        if end_at <= window_start:
            return int((window_start - start_at).total_seconds() // 60)
        if start_at >= window_end:
            return int((start_at - window_end).total_seconds() // 60)
        overflow_before = max(int((window_start - start_at).total_seconds() // 60), 0)
        overflow_after = max(int((end_at - window_end).total_seconds() // 60), 0)
        return overflow_before + overflow_after

    def _load_existing_goal_plan_minutes_by_week(
        self,
        session: Session,
        *,
        user_id: int,
        range_start: datetime,
        range_end: datetime,
        preferences_by_goal: dict[int, AllocationPreferences],
    ) -> dict[tuple[int, date], int]:
        goal_ids = set(preferences_by_goal)
        if not goal_ids:
            return {}

        week_window_start = datetime.combine(range_start.date() - timedelta(days=6), time.min)
        week_window_end = datetime.combine(range_end.date() + timedelta(days=7), time.min)
        items = session.scalars(
            self._active_plan_item_query(user_id).where(
                AIPlanItem.goal_id.in_(goal_ids),
                AIPlanItem.scheduled_start.is_not(None),
                AIPlanItem.scheduled_end.is_not(None),
                AIPlanItem.scheduled_start < week_window_end,
                AIPlanItem.scheduled_end > week_window_start,
            )
        ).all()

        minutes_by_goal_week: dict[tuple[int, date], int] = {}
        for item in items:
            self._add_goal_week_usage(
                minutes_by_goal_week,
                goal_id=item.goal_id,
                start_at=normalize_to_kst_naive(item.scheduled_start),
                end_at=normalize_to_kst_naive(item.scheduled_end),
                preferences=preferences_by_goal.get(item.goal_id, AllocationPreferences()),
            )
        return minutes_by_goal_week

    def _goal_week_has_capacity(
        self,
        goal_minutes_by_week: dict[tuple[int, date], int],
        *,
        goal_id: int,
        start_at: datetime,
        end_at: datetime,
        preferences: AllocationPreferences,
    ) -> bool:
        if preferences.weekly_available_minutes is None:
            return True
        duration = int((end_at - start_at).total_seconds() // 60)
        week_key = (goal_id, self._goal_week_start(start_at.date(), preferences.week_anchor))
        return goal_minutes_by_week.get(week_key, 0) + duration <= preferences.weekly_available_minutes

    def _add_goal_week_usage(
        self,
        goal_minutes_by_week: dict[tuple[int, date], int],
        *,
        goal_id: int,
        start_at: datetime,
        end_at: datetime,
        preferences: AllocationPreferences,
    ) -> None:
        if end_at <= start_at:
            return

        pointer = start_at
        while pointer < end_at:
            next_week = datetime.combine(
                self._goal_week_start(pointer.date(), preferences.week_anchor) + timedelta(days=7),
                time.min,
            )
            chunk_end = min(end_at, next_week)
            minutes = int((chunk_end - pointer).total_seconds() // 60)
            week_key = (goal_id, self._goal_week_start(pointer.date(), preferences.week_anchor))
            goal_minutes_by_week[week_key] = goal_minutes_by_week.get(week_key, 0) + minutes
            pointer = chunk_end

    def _goal_week_start(self, day: date, anchor: date | None) -> date:
        if anchor is None:
            return day - timedelta(days=day.weekday())
        elapsed_days = max((day - anchor).days, 0)
        return anchor + timedelta(days=(elapsed_days // 7) * 7)

    def _as_dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _time_bucket(self, start_at: datetime) -> str:
        if start_at.hour < 12:
            return "morning"
        if start_at.hour < 18:
            return "afternoon"
        return "evening"

    def _active_plan_item_query(self, user_id: int):
        return (
            select(AIPlanItem)
            .join(AIPlan, AIPlanItem.ai_plan_id == AIPlan.id)
            .join(Goal, AIPlanItem.goal_id == Goal.id)
            .where(
                AIPlanItem.user_id == user_id,
                AIPlan.status == PlanStatus.active,
                Goal.status == GoalStatus.active,
            )
        )

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
            select(AllocatedTask).join(FlexibleTask, AllocatedTask.flexible_task_id == FlexibleTask.id).where(
                AllocatedTask.user_id == user_id,
                FlexibleTask.status != FlexibleTaskStatus.cancelled,
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
