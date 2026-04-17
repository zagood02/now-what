from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.init_db import create_db_and_tables
from app.db.session import SessionLocal
from app.models.ai_plan import AIPlan, AIPlanItem
from app.models.enums import GoalCategory, GoalStatus, PlanStatus
from app.models.fixed_schedule import FixedSchedule
from app.models.flexible_task import FlexibleTask
from app.models.goal import Goal
from app.models.user import User
from app.services.allocation import AllocationService
from app.services import planning
from app.services.planning import PlanningService


SAMPLE_EMAIL = "frontend-sample@example.com"
SAMPLE_NAME = "Frontend Sample User"
SAMPLE_TIMEZONE = "Asia/Seoul"


def _at(day: date, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=tz)


def _build_fixed_schedules(user_id: int, tz: ZoneInfo) -> list[FixedSchedule]:
    today = datetime.now(tz).date()
    return [
        FixedSchedule(
            user_id=user_id,
            title="Capstone team sync",
            description="Short project alignment meeting.",
            location="Engineering building room 302",
            start_at=_at(today + timedelta(days=1), 9, 30, tz),
            end_at=_at(today + timedelta(days=1), 10, 0, tz),
        ),
        FixedSchedule(
            user_id=user_id,
            title="Frontend review session",
            description="Design and interaction review with teammates.",
            location="Online",
            start_at=_at(today + timedelta(days=2), 14, 0, tz),
            end_at=_at(today + timedelta(days=2), 15, 30, tz),
        ),
        FixedSchedule(
            user_id=user_id,
            title="Workout",
            description="Personal fixed schedule to block busy time.",
            location="Gym",
            start_at=_at(today + timedelta(days=3), 18, 30, tz),
            end_at=_at(today + timedelta(days=3), 19, 30, tz),
        ),
    ]


def _build_flexible_tasks(user_id: int, tz: ZoneInfo) -> list[FlexibleTask]:
    today = datetime.now(tz).date()
    return [
        FlexibleTask(
            user_id=user_id,
            title="Prepare portfolio case study",
            description="Draft the project background, process, and result sections.",
            estimated_minutes=180,
            min_session_minutes=60,
            preferred_session_minutes=90,
            max_minutes_per_day=180,
            priority=3,
            due_at=_at(today + timedelta(days=4), 22, 0, tz),
            details_json={"tag": "portfolio"},
        ),
        FlexibleTask(
            user_id=user_id,
            title="Polish UI backlog",
            description="Apply spacing, typography, and interaction fixes.",
            estimated_minutes=120,
            min_session_minutes=30,
            preferred_session_minutes=60,
            max_minutes_per_day=120,
            priority=2,
            due_at=_at(today + timedelta(days=5), 21, 0, tz),
            details_json={"tag": "frontend"},
        ),
        FlexibleTask(
            user_id=user_id,
            title="Read capstone references",
            description="Review 2-3 relevant references and summarize notes.",
            estimated_minutes=90,
            min_session_minutes=30,
            preferred_session_minutes=45,
            max_minutes_per_day=90,
            priority=1,
            due_at=_at(today + timedelta(days=6), 20, 0, tz),
            details_json={"tag": "research"},
        ),
    ]


def _build_goal(user_id: int) -> Goal:
    return Goal(
        user_id=user_id,
        title="Launch capstone demo page",
        description="Prepare a presentable demo flow for the capstone review.",
        category=GoalCategory.work,
        status=GoalStatus.active,
        target_date=date.today() + timedelta(days=10),
        details_json={"audience": "professors and teammates"},
        answers_json={
            "weekly_available_hours": 8,
            "constraints": "Weekdays are easier after 7pm. Weekend mornings are available.",
            "deliverables": "Landing page, demo walkthrough, and short explanation notes.",
        },
    )


def _create_template_plan(goal: Goal) -> tuple[AIPlan, list[AIPlanItem]]:
    original_model = planning.settings.llm_model
    original_key = planning.settings.gemini_api_key

    try:
        planning.settings.llm_model = "template-fallback"
        planning.settings.gemini_api_key = None
        draft = PlanningService().build_plan(goal, goal.answers_json)
    finally:
        planning.settings.llm_model = original_model
        planning.settings.gemini_api_key = original_key

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

    items = [
        AIPlanItem(
            ai_plan_id=0,
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
        for item in draft.items
    ]
    return plan, items


def main() -> None:
    tz = ZoneInfo(SAMPLE_TIMEZONE)
    create_db_and_tables()

    with SessionLocal() as session:
        existing_user = session.scalar(select(User).where(User.email == SAMPLE_EMAIL))
        if existing_user:
            session.delete(existing_user)
            session.commit()

        user = User(email=SAMPLE_EMAIL, name=SAMPLE_NAME, timezone=SAMPLE_TIMEZONE)
        session.add(user)
        session.flush()

        fixed_schedules = _build_fixed_schedules(user.id, tz)
        flexible_tasks = _build_flexible_tasks(user.id, tz)
        goal = _build_goal(user.id)

        session.add_all(fixed_schedules)
        session.add_all(flexible_tasks)
        session.add(goal)
        session.flush()

        plan, plan_items = _create_template_plan(goal)
        session.add(plan)
        session.flush()

        for item in plan_items:
            item.ai_plan_id = plan.id
            session.add(item)

        session.flush()

        range_start = _at(datetime.now(tz).date(), 6, 0, tz)
        range_end = _at(datetime.now(tz).date() + timedelta(days=7), 23, 0, tz)

        AllocationService().allocate(
            session,
            user_id=user.id,
            range_start=range_start,
            range_end=range_end,
            day_start=time(6, 0),
            day_end=time(23, 0),
            clear_existing=True,
        )
        session.commit()

        print("Seeded frontend sample data successfully.")
        print(f"user_id={user.id}")
        print(f"sample_email={SAMPLE_EMAIL}")
        print(f"goal_id={goal.id}")
        print("")
        print("Suggested API checks:")
        print(f"GET /api/v1/users/{user.id}")
        print(f"GET /api/v1/schedules/fixed?user_id={user.id}")
        print(f"GET /api/v1/tasks/flexible?user_id={user.id}")
        print(f"GET /api/v1/goals?user_id={user.id}")
        print(
            "GET /api/v1/calendar?"
            f"user_id={user.id}&start={range_start.isoformat()}&end={range_end.isoformat()}"
        )


if __name__ == "__main__":
    main()
