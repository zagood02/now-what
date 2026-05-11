from datetime import datetime, time, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.models import AllocatedTask, FixedSchedule, FlexibleTask, User
from backend.models.base import Base
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
        )

        assert [(item.scheduled_start, item.scheduled_end, item.duration_minutes) for item in result.allocated_tasks] == [
            (datetime(2026, 1, 1, 11), datetime(2026, 1, 1, 11, 30), 30)
        ]
        assert result.unscheduled_task_ids == [task.id]
