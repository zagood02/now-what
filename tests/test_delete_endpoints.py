from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.auth import create_access_token
from backend.db.session import get_db_session
from backend.main import app
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.allocated_task import AllocatedTask
from backend.models.base import Base
from backend.models.enums import FlexibleTaskStatus, GoalCategory, GoalStatus, PlanItemStatus, PlanStatus
from backend.models.flexible_task import FlexibleTask
from backend.models.goal import Goal
from backend.models.user import User


def _client_with_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db():
        with session_local() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app), session_local


def _create_user(session: Session) -> User:
    user = User(
        email="delete@example.com",
        name="Delete User",
        hashed_password="x",
        timezone="Asia/Seoul",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_delete_allocated_task_only_removes_scheduled_chunk():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session)
            task = FlexibleTask(
                user_id=user.id,
                title="Study block",
                estimated_minutes=60,
                min_session_minutes=30,
                preferred_session_minutes=60,
                max_minutes_per_day=120,
                priority=2,
                status=FlexibleTaskStatus.scheduled,
                details_json={},
            )
            session.add(task)
            session.flush()
            allocation = AllocatedTask(
                user_id=user.id,
                flexible_task_id=task.id,
                title_snapshot=task.title,
                scheduled_start=datetime(2026, 5, 1, 9),
                scheduled_end=datetime(2026, 5, 1, 10),
                duration_minutes=60,
            )
            session.add(allocation)
            session.commit()
            token = create_access_token(user.id)
            allocation_id = allocation.id
            task_id = task.id

        response = client.delete(
            f"/api/v1/tasks/flexible/allocations/{allocation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        with session_local() as session:
            assert session.get(AllocatedTask, allocation_id) is None
            assert session.get(FlexibleTask, task_id).status == FlexibleTaskStatus.pending
    finally:
        app.dependency_overrides.clear()


def test_plan_item_unschedule_skip_and_goal_delete():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session)
            goal = Goal(
                user_id=user.id,
                title="Capstone",
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
            item = AIPlanItem(
                ai_plan_id=plan.id,
                goal_id=goal.id,
                user_id=user.id,
                title="Write demo",
                item_type="work",
                estimated_minutes=60,
                priority=2,
                target_date=date(2026, 5, 2),
                is_schedulable=True,
                scheduled_start=datetime(2026, 5, 1, 9),
                scheduled_end=datetime(2026, 5, 1, 10),
                status=PlanItemStatus.scheduled,
                metadata_json={},
            )
            session.add(item)
            session.commit()
            token = create_access_token(user.id)
            goal_id = goal.id
            plan_id = plan.id
            item_id = item.id

        unschedule_response = client.delete(
            f"/api/v1/planner/plan-items/{item_id}/schedule",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert unschedule_response.status_code == 200
        assert unschedule_response.json()["status"] == "suggested"
        assert unschedule_response.json()["scheduled_start"] is None

        skip_response = client.post(
            f"/api/v1/planner/plan-items/{item_id}/skip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert skip_response.status_code == 200
        assert skip_response.json()["status"] == "skipped"

        delete_goal_response = client.delete(
            f"/api/v1/goals/{goal_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_goal_response.status_code == 200

        with session_local() as session:
            assert session.get(Goal, goal_id) is None
            assert session.get(AIPlan, plan_id) is None
            assert session.get(AIPlanItem, item_id) is None
    finally:
        app.dependency_overrides.clear()
