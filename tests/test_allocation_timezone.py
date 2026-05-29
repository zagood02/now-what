from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.models import AllocatedTask, FixedSchedule, FlexibleTask, User
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.base import Base
from backend.models.enums import GoalCategory, GoalStatus, PlanItemStatus, PlanStatus
from backend.models.goal import Goal
from backend.services.allocation import AllocationConflictError, AllocationService
from backend.services.calendar import CalendarService


def test_merge_intervals_normalizes_mixed_timezone_values():
    service = AllocationService()

    merged = service._merge_intervals(
        [
            (datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 10)),
            (
                datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            ),
        ]
    )

    assert merged == [(datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 10))]


def test_allocation_split_chunks_use_five_minute_units_without_label_stacking():
    service = AllocationService()

    assert service._split_minutes(100, 45) == [35, 35, 30]
    assert service._split_item_title("Deep work (1/2)", 1, 3) == "Deep work (1/3)"
    assert (
        service._split_item_description("Base description\n\n분할된 일정 1/2입니다.", 1, 3)
        == "Base description"
    )


def test_allocation_revalidates_candidate_before_writing():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="revalidate@example.com",
            name="Revalidate",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Concurrent task",
            estimated_minutes=60,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=3,
            due_at=datetime(2026, 1, 1, 12),
            details_json={},
        )
        session.add(task)
        session.commit()

        service = AllocationService()
        load_calls = 0

        def load_busy_slots(session, user_id, range_start, range_end):
            nonlocal load_calls
            load_calls += 1
            if load_calls == 1:
                return []
            return [(range_start, range_end)]

        service._load_busy_slots = load_busy_slots

        with pytest.raises(AllocationConflictError, match="Schedule changed during allocation"):
            service.allocate(
                session,
                user_id=user.id,
                range_start=datetime(2026, 1, 1, 9),
                range_end=datetime(2026, 1, 1, 12),
                day_start=time(9),
                day_end=time(12),
                buffer_minutes=0,
                max_auto_minutes_per_day=120,
            )

        assert session.query(AllocatedTask).count() == 0


def test_allocation_respects_existing_daily_minutes():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="demo@example.com",
            name="Demo",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Capstone task",
            estimated_minutes=120,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=90,
            priority=3,
            due_at=datetime(2026, 1, 1, 15),
            details_json={},
        )
        session.add(task)
        session.flush()

        session.add(
            FixedSchedule(
                user_id=user.id,
                title="Class",
                start_at=datetime(2026, 1, 1, 10),
                end_at=datetime(2026, 1, 1, 11),
                is_all_day=False,
            )
        )
        session.add(
            AllocatedTask(
                user_id=user.id,
                flexible_task_id=task.id,
                title_snapshot=task.title,
                scheduled_start=datetime(2026, 1, 1, 9),
                scheduled_end=datetime(2026, 1, 1, 10),
                duration_minutes=60,
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
            range_end=datetime(2026, 1, 1, 6, tzinfo=timezone.utc),
            day_start=time(9),
            day_end=time(15),
            clear_existing=False,
        )

        assert [(item.scheduled_start, item.scheduled_end, item.duration_minutes) for item in result.allocated_tasks] == [
            (datetime(2026, 1, 1, 14), datetime(2026, 1, 1, 14, 30), 30)
        ]
        assert result.unscheduled_task_ids == [task.id]


def test_busy_slot_loading_ignores_allocations_outside_requested_range():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="busy-filter@example.com",
            name="Busy Filter",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Far future task",
            estimated_minutes=60,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=3,
            details_json={},
        )
        session.add(task)
        session.flush()

        session.add(
            AllocatedTask(
                user_id=user.id,
                flexible_task_id=task.id,
                title_snapshot=task.title,
                scheduled_start=datetime(2030, 1, 1, 9),
                scheduled_end=datetime(2030, 1, 1, 10),
                duration_minutes=60,
            )
        )
        session.commit()

        busy_slots = AllocationService()._load_busy_slots(
            session,
            user.id,
            datetime(2026, 1, 1, 9),
            datetime(2026, 1, 1, 18),
        )

        assert busy_slots == []


def test_allocation_rebuilds_existing_auto_allocations_by_default():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="rebuild@example.com",
            name="Rebuild",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Rebuild task",
            estimated_minutes=120,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=180,
            priority=3,
            due_at=datetime(2026, 1, 1, 15),
            details_json={},
        )
        session.add(task)
        session.flush()

        session.add(
            FixedSchedule(
                user_id=user.id,
                title="Class",
                start_at=datetime(2026, 1, 1, 10),
                end_at=datetime(2026, 1, 1, 11),
                is_all_day=False,
            )
        )
        session.add(
            AllocatedTask(
                user_id=user.id,
                flexible_task_id=task.id,
                title_snapshot=task.title,
                scheduled_start=datetime(2026, 1, 1, 9),
                scheduled_end=datetime(2026, 1, 1, 10),
                duration_minutes=60,
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 13),
            day_start=time(9),
            day_end=time(13),
            buffer_minutes=0,
        )
        session.commit()

        assert [(item.scheduled_start, item.scheduled_end, item.duration_minutes) for item in result.allocated_tasks] == [
            (datetime(2026, 1, 1, 11), datetime(2026, 1, 1, 12), 60),
            (datetime(2026, 1, 1, 12), datetime(2026, 1, 1, 13), 60),
        ]
        assert result.unscheduled_task_ids == []


def test_allocation_adds_buffer_between_auto_sessions():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="buffer@example.com",
            name="Buffer",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Buffered task",
            estimated_minutes=120,
            min_session_minutes=60,
            preferred_session_minutes=60,
            max_minutes_per_day=180,
            priority=3,
            due_at=datetime(2026, 1, 1, 18),
            details_json={},
        )
        session.add(task)
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=30,
        )

        windows = [(item.scheduled_start, item.scheduled_end) for item in result.allocated_tasks]
        assert windows == [
            (datetime(2026, 1, 1, 11, 30), datetime(2026, 1, 1, 12, 30)),
            (datetime(2026, 1, 1, 14), datetime(2026, 1, 1, 15)),
        ]
        assert windows[1][0] - windows[0][1] >= timedelta(minutes=30)


def test_allocation_limits_total_auto_minutes_per_day():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="limit@example.com",
            name="Limit",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Large task",
            estimated_minutes=300,
            min_session_minutes=60,
            preferred_session_minutes=60,
            max_minutes_per_day=300,
            priority=3,
            due_at=datetime(2026, 1, 1, 22),
            details_json={},
        )
        session.add(task)
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 22),
            day_start=time(9),
            day_end=time(22),
            buffer_minutes=0,
            max_auto_minutes_per_day=120,
        )

        assert sum(item.duration_minutes for item in result.allocated_tasks) == 120
        assert result.unscheduled_task_ids == [task.id]


def test_allocation_ignores_archived_plan_items():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="archived-plan@example.com",
            name="Archived Plan",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        active_goal = Goal(
            user_id=user.id,
            title="Active goal",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        archived_goal = Goal(
            user_id=user.id,
            title="Archived goal",
            category=GoalCategory.work,
            status=GoalStatus.archived,
            details_json={},
            answers_json={},
        )
        session.add_all([active_goal, archived_goal])
        session.flush()

        active_plan = AIPlan(
            user_id=user.id,
            goal_id=active_goal.id,
            summary="active",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        archived_plan = AIPlan(
            user_id=user.id,
            goal_id=archived_goal.id,
            summary="archived",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.archived,
        )
        session.add_all([active_plan, archived_plan])
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=active_goal.id,
                    ai_plan_id=active_plan.id,
                    title="Active plan item",
                    item_type="work",
                    estimated_minutes=60,
                    priority=2,
                    is_schedulable=True,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=archived_goal.id,
                    ai_plan_id=archived_plan.id,
                    title="Archived plan item",
                    item_type="stale",
                    estimated_minutes=60,
                    priority=3,
                    is_schedulable=True,
                    metadata_json={},
                ),
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 13),
            day_start=time(9),
            day_end=time(13),
            buffer_minutes=0,
        )

        assert [item.title for item in result.scheduled_plan_items] == ["Active plan item"]


def test_plan_items_prefer_slots_near_target_date():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="target-date-plan@example.com",
            name="Target Date Plan",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Presentation",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="presentation",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Outline slides",
                    item_type="planning",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 1, 6),
                    is_schedulable=True,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Practice demo",
                    item_type="practice",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 1, 8),
                    is_schedulable=True,
                    metadata_json={},
                ),
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 8, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        scheduled_by_title = {item.title: item.scheduled_start.date() for item in result.scheduled_plan_items}
        assert scheduled_by_title == {
            "Outline slides": date(2026, 1, 6),
            "Practice demo": date(2026, 1, 8),
        }


def test_plan_item_target_date_is_preference_not_hard_deadline():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="target-preference@example.com",
            name="Target Preference",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Goal deadline",
            category=GoalCategory.work,
            status=GoalStatus.active,
            target_date=date(2026, 1, 10),
            details_json={},
            answers_json={},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Late but still valid",
                item_type="work",
                estimated_minutes=60,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 6, 9),
            range_end=datetime(2026, 1, 6, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        assert [item.title for item in result.scheduled_plan_items] == ["Late but still valid"]
        assert result.unscheduled_plan_item_ids == []


def test_short_plan_items_spread_across_available_days():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="spread-short@example.com",
            name="Spread Short",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Spread short work",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title=f"Short work {index}",
                    item_type="work",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 1, 6),
                    is_schedulable=True,
                    metadata_json={},
                )
                for index in range(1, 4)
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 7, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        scheduled_dates = {item.scheduled_start.date() for item in result.scheduled_plan_items}
        assert scheduled_dates == {date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)}


def test_plan_item_daily_count_balance_beats_target_date_tiebreaker():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="daily-count-balance@example.com",
            name="Daily Count Balance",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Balance by count",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="balance",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="One existing block",
                    item_type="work",
                    estimated_minutes=60,
                    priority=3,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 1, 5, 9),
                    scheduled_end=datetime(2026, 1, 5, 10),
                    status=PlanItemStatus.scheduled,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Existing short block A",
                    item_type="work",
                    estimated_minutes=30,
                    priority=3,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 1, 6, 9),
                    scheduled_end=datetime(2026, 1, 6, 9, 30),
                    status=PlanItemStatus.scheduled,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Existing short block B",
                    item_type="work",
                    estimated_minutes=30,
                    priority=3,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 1, 6, 10),
                    scheduled_end=datetime(2026, 1, 6, 10, 30),
                    status=PlanItemStatus.scheduled,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="New work",
                    item_type="work",
                    estimated_minutes=30,
                    priority=3,
                    target_date=date(2026, 1, 6),
                    is_schedulable=True,
                    metadata_json={},
                ),
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 6, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
            clear_existing=False,
        )

        scheduled = {item.title: item for item in result.scheduled_plan_items}
        assert scheduled["New work"].scheduled_start.date() == date(2026, 1, 5)


def test_structured_preferred_windows_prioritize_matching_plan_item_slots():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="structured-preferred-window@example.com",
            name="Structured Preferred Window",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Evening study",
            category=GoalCategory.study,
            status=GoalStatus.active,
            details_json={},
            answers_json={
                "allocation_preferences": {
                    "preferred_windows": [
                        {"days": [0], "start": "18:00", "end": "22:00"},
                    ],
                }
            },
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="study",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Review notes",
                item_type="study",
                estimated_minutes=60,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 22),
            day_start=time(9),
            day_end=time(22),
            buffer_minutes=0,
        )

        assert len(result.scheduled_plan_items) == 1
        assert result.scheduled_plan_items[0].scheduled_start == datetime(2026, 1, 5, 18)


def test_structured_avoid_windows_exclude_and_penalize_nearby_plan_item_slots():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="structured-avoid-window@example.com",
            name="Structured Avoid Window",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Avoid afternoon",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={
                "allocation_preferences": {
                    "avoid_windows": [
                        {"days": [0], "start": "13:00", "end": "18:00"},
                    ],
                }
            },
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Draft memo",
                item_type="work",
                estimated_minutes=60,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        assert len(result.scheduled_plan_items) == 1
        assert result.scheduled_plan_items[0].scheduled_start == datetime(2026, 1, 5, 10)


def test_overnight_structured_windows_apply_to_following_day():
    service = AllocationService()

    preferences = service._allocation_preferences_from_answers(
        {
            "allocation_preferences": {
                "avoid_windows": [
                    {"days": [0], "start": "22:00", "end": "02:00"},
                ],
            }
        }
    )

    assert [
        (window.days, window.start, window.end)
        for window in preferences.avoid_windows
    ] == [
        (frozenset({0}), time(22), time(23, 59)),
        (frozenset({1}), time.min, time(2)),
    ]


def test_explicit_weekday_daily_limits_are_hard_constraints():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="weekday-hard-limits@example.com",
            name="Weekday Hard Limits",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Limited weekday work",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={
                "allocation_preferences": {
                    "max_weekday_items_per_day": 2,
                    "max_weekday_minutes_per_day": 90,
                }
            },
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title=f"Limited work {index}",
                    item_type="work",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 1, 5),
                    is_schedulable=True,
                    metadata_json={},
                )
                for index in range(1, 3)
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        assert len(result.scheduled_plan_items) == 1
        assert len(result.unscheduled_plan_item_ids) == 1


def test_goal_answers_preferred_work_times_prioritize_plan_item_allocation():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="preferred-window@example.com",
            name="Preferred Window",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Evening study",
            category=GoalCategory.study,
            status=GoalStatus.active,
            details_json={},
            answers_json={"preferred_work_times": "평일 저녁 7-10시"},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="study",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Review notes",
                item_type="study",
                estimated_minutes=60,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 22),
            day_start=time(9),
            day_end=time(22),
            buffer_minutes=0,
        )

        assert len(result.scheduled_plan_items) == 1
        assert result.scheduled_plan_items[0].scheduled_start == datetime(2026, 1, 5, 19)


def test_goal_answers_unavailable_times_block_plan_item_allocation():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="avoid-window@example.com",
            name="Avoid Window",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Avoid afternoon",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={"unavailable_times": "오후 1-6시"},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Draft memo",
                item_type="work",
                estimated_minutes=60,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        assert len(result.scheduled_plan_items) == 1
        assert result.scheduled_plan_items[0].scheduled_start == datetime(2026, 1, 5, 10)


def test_goal_answers_weekly_available_hours_limit_plan_item_allocation():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="weekly-limit@example.com",
            name="Weekly Limit",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Small week",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={"weekly_available_hours": 1},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="First hour",
                    item_type="work",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 1, 5),
                    is_schedulable=True,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Second hour",
                    item_type="work",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 1, 5),
                    is_schedulable=True,
                    metadata_json={},
                ),
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        assert [item.title for item in result.scheduled_plan_items] == ["First hour"]
        assert len(result.unscheduled_plan_item_ids) == 1


def test_goal_weekly_limit_uses_goal_created_date_rolling_window():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="rolling-week@example.com",
            name="Rolling Week",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Rolling weekly cap",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={"weekly_available_hours": 8},
            created_at=datetime(2026, 5, 27, 9),
            updated_at=datetime(2026, 5, 27, 9),
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Existing first-window work",
                    item_type="work",
                    estimated_minutes=480,
                    priority=3,
                    target_date=date(2026, 6, 2),
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 6, 1, 9),
                    scheduled_end=datetime(2026, 6, 1, 17),
                    status=PlanItemStatus.scheduled,
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=goal.id,
                    ai_plan_id=plan.id,
                    title="Second-window work",
                    item_type="work",
                    estimated_minutes=60,
                    priority=3,
                    target_date=date(2026, 6, 4),
                    is_schedulable=True,
                    metadata_json={},
                ),
            ]
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 6, 3, 9),
            range_end=datetime(2026, 6, 4, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
            clear_existing=False,
        )

        assert [item.title for item in result.scheduled_plan_items] == ["Second-window work"]
        assert result.scheduled_plan_items[0].scheduled_start.date() <= date(2026, 6, 4)


def test_plan_items_remain_unscheduled_when_calendar_is_full_before_deadline():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="full-calendar@example.com",
            name="Full Calendar",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        session.add(
            FixedSchedule(
                user_id=user.id,
                title="All-day work block",
                start_at=datetime(2026, 1, 5, 9),
                end_at=datetime(2026, 1, 5, 18),
                is_all_day=False,
            )
        )

        goal = Goal(
            user_id=user.id,
            title="Blocked goal",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={"weekly_available_hours": 4},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="work",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        item = AIPlanItem(
            user_id=user.id,
            goal_id=goal.id,
            ai_plan_id=plan.id,
            title="Needs free time",
            item_type="work",
            estimated_minutes=60,
            priority=3,
            target_date=date(2026, 1, 5),
            is_schedulable=True,
            metadata_json={},
        )
        session.add(item)
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        assert result.scheduled_plan_items == []
        assert result.unscheduled_plan_item_ids == [item.id]


def test_goal_answers_session_preference_splits_long_plan_items():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="session-preference@example.com",
            name="Session Preference",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Short sessions",
            category=GoalCategory.study,
            status=GoalStatus.active,
            details_json={},
            answers_json={"session_preference": "짧게 자주 25-45분"},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="study",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Long review",
                item_type="study",
                estimated_minutes=90,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 12),
            day_start=time(9),
            day_end=time(12),
            buffer_minutes=0,
        )

        durations = [
            int((item.scheduled_end - item.scheduled_start).total_seconds() // 60)
            for item in result.scheduled_plan_items
        ]
        assert durations == [45, 45]
        assert [item.metadata_json["split_part"] for item in result.scheduled_plan_items] == [1, 2]


def test_oversized_plan_items_are_split_before_allocation():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="split-plan@example.com",
            name="Split Plan",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Research",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        session.add(goal)
        session.flush()

        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="research",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()

        session.add(
            AIPlanItem(
                user_id=user.id,
                goal_id=goal.id,
                ai_plan_id=plan.id,
                title="Long research block",
                item_type="deep_work",
                estimated_minutes=300,
                priority=3,
                target_date=date(2026, 1, 5),
                is_schedulable=True,
                metadata_json={},
            )
        )
        session.commit()

        service = AllocationService()
        result = service.allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 5, 9),
            range_end=datetime(2026, 1, 5, 18),
            day_start=time(9),
            day_end=time(18),
            buffer_minutes=0,
        )

        durations = [
            int((item.scheduled_end - item.scheduled_start).total_seconds() // 60)
            for item in result.scheduled_plan_items
        ]

        assert durations == [100, 100, 100]
        assert all(duration <= service.max_plan_item_session_minutes for duration in durations)
        assert [item.metadata_json["split_part"] for item in result.scheduled_plan_items] == [1, 2, 3]
        assert sum(durations) == 300


def test_calendar_ignores_scheduled_items_from_archived_plans():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="calendar-archived-plan@example.com",
            name="Calendar Archived Plan",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        active_goal = Goal(
            user_id=user.id,
            title="Active goal",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        archived_goal = Goal(
            user_id=user.id,
            title="Archived goal",
            category=GoalCategory.work,
            status=GoalStatus.archived,
            details_json={},
            answers_json={},
        )
        session.add_all([active_goal, archived_goal])
        session.flush()

        active_plan = AIPlan(
            user_id=user.id,
            goal_id=active_goal.id,
            summary="active",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.active,
        )
        archived_plan = AIPlan(
            user_id=user.id,
            goal_id=archived_goal.id,
            summary="archived",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            status=PlanStatus.archived,
        )
        session.add_all([active_plan, archived_plan])
        session.flush()

        session.add_all(
            [
                AIPlanItem(
                    user_id=user.id,
                    goal_id=active_goal.id,
                    ai_plan_id=active_plan.id,
                    title="Active scheduled item",
                    item_type="work",
                    estimated_minutes=60,
                    priority=2,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 1, 1, 10),
                    scheduled_end=datetime(2026, 1, 1, 11),
                    metadata_json={},
                ),
                AIPlanItem(
                    user_id=user.id,
                    goal_id=archived_goal.id,
                    ai_plan_id=archived_plan.id,
                    title="Archived scheduled item",
                    item_type="stale",
                    estimated_minutes=60,
                    priority=3,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 1, 1, 11),
                    scheduled_end=datetime(2026, 1, 1, 12),
                    metadata_json={},
                ),
            ]
        )
        session.commit()

        calendar = CalendarService().build(
            session,
            user_id=user.id,
            start=datetime(2026, 1, 1, 9),
            end=datetime(2026, 1, 1, 13),
        )

        assert [event.title for event in calendar.events] == ["Active scheduled item"]
        assert calendar.events[0].metadata_json["goal_id"] == active_goal.id
        assert calendar.events[0].metadata_json["goal_title"] == "Active goal"
        assert calendar.events[0].metadata_json["ai_plan_id"] == active_plan.id
        assert calendar.events[0].metadata_json["item_type"] == "work"
