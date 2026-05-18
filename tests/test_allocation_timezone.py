from datetime import datetime, time, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.models import AllocatedTask, FixedSchedule, FlexibleTask, User
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.base import Base
from backend.models.enums import FlexibleTaskStatus, GoalCategory, GoalStatus, PlanItemStatus, PlanStatus
from backend.models.goal import Goal
from backend.services.allocation import AllocationService


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


def test_allocation_keeps_completed_and_cancelled_task_allocations_when_rebuilding():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="preserve-complete@example.com",
            name="Preserve Complete",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        completed_task = FlexibleTask(
            user_id=user.id,
            title="Completed task",
            estimated_minutes=60,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=3,
            status=FlexibleTaskStatus.completed,
            details_json={},
        )
        cancelled_task = FlexibleTask(
            user_id=user.id,
            title="Cancelled task",
            estimated_minutes=60,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=3,
            status=FlexibleTaskStatus.cancelled,
            details_json={},
        )
        pending_task = FlexibleTask(
            user_id=user.id,
            title="Pending task",
            estimated_minutes=60,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=3,
            due_at=datetime(2026, 1, 1, 12),
            details_json={},
        )
        session.add_all([completed_task, cancelled_task, pending_task])
        session.flush()
        completed_allocation = AllocatedTask(
            user_id=user.id,
            flexible_task_id=completed_task.id,
            title_snapshot=completed_task.title,
            scheduled_start=datetime(2026, 1, 1, 9),
            scheduled_end=datetime(2026, 1, 1, 10),
            duration_minutes=60,
        )
        cancelled_allocation = AllocatedTask(
            user_id=user.id,
            flexible_task_id=cancelled_task.id,
            title_snapshot=cancelled_task.title,
            scheduled_start=datetime(2026, 1, 1, 10),
            scheduled_end=datetime(2026, 1, 1, 11),
            duration_minutes=60,
        )
        session.add_all([completed_allocation, cancelled_allocation])
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 12),
            day_start=time(9),
            day_end=time(12),
            buffer_minutes=0,
            clear_existing=True,
        )
        session.commit()

        assert session.get(AllocatedTask, completed_allocation.id) is not None
        assert session.get(AllocatedTask, cancelled_allocation.id) is not None
        assert [(item.flexible_task_id, item.scheduled_start, item.scheduled_end) for item in result.allocated_tasks] == [
            (pending_task.id, datetime(2026, 1, 1, 11), datetime(2026, 1, 1, 12))
        ]


def test_allocation_preserves_existing_allocations_when_clear_existing_is_false():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="preserve-existing@example.com",
            name="Preserve Existing",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Two hour task",
            estimated_minutes=120,
            min_session_minutes=60,
            preferred_session_minutes=60,
            max_minutes_per_day=180,
            priority=3,
            due_at=datetime(2026, 1, 1, 12),
            details_json={},
        )
        session.add(task)
        session.flush()
        existing_allocation = AllocatedTask(
            user_id=user.id,
            flexible_task_id=task.id,
            title_snapshot=task.title,
            scheduled_start=datetime(2026, 1, 1, 9),
            scheduled_end=datetime(2026, 1, 1, 10),
            duration_minutes=60,
        )
        session.add(existing_allocation)
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 12),
            day_start=time(9),
            day_end=time(12),
            buffer_minutes=0,
            clear_existing=False,
        )
        session.commit()

        assert session.get(AllocatedTask, existing_allocation.id) is not None
        assert [(item.scheduled_start, item.scheduled_end, item.duration_minutes) for item in result.allocated_tasks] == [
            (datetime(2026, 1, 1, 11), datetime(2026, 1, 1, 12), 60)
        ]


def test_allocation_avoids_overlap_between_flexible_tasks_and_plan_items_in_same_run():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="mixed-allocation@example.com",
            name="Mixed Allocation",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        task = FlexibleTask(
            user_id=user.id,
            title="Flexible work",
            estimated_minutes=60,
            min_session_minutes=60,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=3,
            due_at=datetime(2026, 1, 1, 11),
            details_json={},
        )
        goal = Goal(
            user_id=user.id,
            title="Plan goal",
            category=GoalCategory.work,
            status=GoalStatus.active,
            details_json={},
            answers_json={},
        )
        session.add_all([task, goal])
        session.flush()
        plan = AIPlan(
            user_id=user.id,
            goal_id=goal.id,
            summary="Plan",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            llm_mode="template-fallback",
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()
        item = AIPlanItem(
            ai_plan_id=plan.id,
            goal_id=goal.id,
            user_id=user.id,
            title="Plan work",
            item_type="work",
            estimated_minutes=60,
            priority=3,
            is_schedulable=True,
            status=PlanItemStatus.suggested,
            metadata_json={},
        )
        session.add(item)
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 11),
            day_start=time(9),
            day_end=time(11),
            buffer_minutes=0,
        )
        session.commit()

        assert len(result.allocated_tasks) == 1
        assert len(result.scheduled_plan_items) == 1
        task_window = (result.allocated_tasks[0].scheduled_start, result.allocated_tasks[0].scheduled_end)
        item_window = (result.scheduled_plan_items[0].scheduled_start, result.scheduled_plan_items[0].scheduled_end)
        assert task_window[1] <= item_window[0] or item_window[1] <= task_window[0]


def test_allocation_keeps_completed_and_skipped_plan_items_when_rebuilding():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="plan-status@example.com",
            name="Plan Status",
            hashed_password="x",
            timezone="Asia/Seoul",
        )
        session.add(user)
        session.flush()

        goal = Goal(
            user_id=user.id,
            title="Goal",
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
            summary="Plan",
            strategy_json={},
            recommendations_json={},
            raw_plan_json={},
            llm_mode="template-fallback",
            status=PlanStatus.active,
        )
        session.add(plan)
        session.flush()
        completed_item = AIPlanItem(
            ai_plan_id=plan.id,
            goal_id=goal.id,
            user_id=user.id,
            title="Completed item",
            item_type="work",
            estimated_minutes=60,
            priority=3,
            is_schedulable=True,
            scheduled_start=datetime(2026, 1, 1, 9),
            scheduled_end=datetime(2026, 1, 1, 10),
            status=PlanItemStatus.completed,
            metadata_json={},
        )
        skipped_item = AIPlanItem(
            ai_plan_id=plan.id,
            goal_id=goal.id,
            user_id=user.id,
            title="Skipped item",
            item_type="work",
            estimated_minutes=60,
            priority=3,
            is_schedulable=True,
            scheduled_start=datetime(2026, 1, 1, 10),
            scheduled_end=datetime(2026, 1, 1, 11),
            status=PlanItemStatus.skipped,
            metadata_json={},
        )
        suggested_item = AIPlanItem(
            ai_plan_id=plan.id,
            goal_id=goal.id,
            user_id=user.id,
            title="Suggested item",
            item_type="work",
            estimated_minutes=60,
            priority=3,
            is_schedulable=True,
            status=PlanItemStatus.suggested,
            metadata_json={},
        )
        session.add_all([completed_item, skipped_item, suggested_item])
        session.commit()

        result = AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=datetime(2026, 1, 1, 9),
            range_end=datetime(2026, 1, 1, 12),
            day_start=time(9),
            day_end=time(12),
            buffer_minutes=0,
            clear_existing=True,
        )
        session.commit()

        assert session.get(AIPlanItem, completed_item.id).scheduled_start == datetime(2026, 1, 1, 9)
        assert session.get(AIPlanItem, skipped_item.id).scheduled_start == datetime(2026, 1, 1, 10)
        assert [(item.id, item.scheduled_start, item.scheduled_end) for item in result.scheduled_plan_items] == [
            (suggested_item.id, datetime(2026, 1, 1, 11), datetime(2026, 1, 1, 12))
        ]
