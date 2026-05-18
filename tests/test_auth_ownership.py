from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.auth import create_access_token
from backend.db.session import get_db_session
from backend.main import app
from backend.models.ai_plan import AIPlan, AIPlanItem
from backend.models.base import Base
from backend.models.enums import GoalCategory, GoalStatus, PlanItemStatus, PlanStatus
from backend.models.fixed_schedule import FixedSchedule
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


def _create_user(session: Session, email: str) -> User:
    user = User(
        email=email,
        name=email.split("@")[0],
        hashed_password="x",
        timezone="Asia/Seoul",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_create_routes_ignore_payload_user_id_and_use_token_user():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            owner = _create_user(session, "owner@example.com")
            other = _create_user(session, "other@example.com")
            token = create_access_token(owner.id)

        fixed_response = client.post(
            "/api/v1/schedules/fixed",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "user_id": other.id,
                "title": "Payload should not own this",
                "start_at": "2026-05-19T09:00:00+09:00",
                "end_at": "2026-05-19T10:00:00+09:00",
            },
        )
        task_response = client.post(
            "/api/v1/tasks/flexible",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "user_id": other.id,
                "title": "Token-owned task",
                "estimated_minutes": 60,
            },
        )
        goal_response = client.post(
            "/api/v1/goals",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "user_id": other.id,
                "title": "Token-owned goal",
                "category": "work",
            },
        )

        assert fixed_response.status_code == 201
        assert fixed_response.json()["user_id"] == owner.id
        assert task_response.status_code == 201
        assert task_response.json()["user_id"] == owner.id
        assert goal_response.status_code == 201
        assert goal_response.json()["user_id"] == owner.id

        with session_local() as session:
            assert session.get(FixedSchedule, fixed_response.json()["id"]).user_id == owner.id
            assert session.get(FlexibleTask, task_response.json()["id"]).user_id == owner.id
            assert session.get(Goal, goal_response.json()["id"]).user_id == owner.id
    finally:
        app.dependency_overrides.clear()


def test_other_users_resources_are_hidden_from_mutation_routes():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            requester = _create_user(session, "requester@example.com")
            owner = _create_user(session, "resource-owner@example.com")
            fixed = FixedSchedule(
                user_id=owner.id,
                title="Private class",
                start_at=datetime(2026, 5, 19, 9),
                end_at=datetime(2026, 5, 19, 10),
                is_all_day=False,
            )
            task = FlexibleTask(
                user_id=owner.id,
                title="Private task",
                estimated_minutes=60,
                min_session_minutes=30,
                preferred_session_minutes=60,
                max_minutes_per_day=120,
                priority=2,
                details_json={},
            )
            goal = Goal(
                user_id=owner.id,
                title="Private goal",
                category=GoalCategory.work,
                status=GoalStatus.active,
                details_json={},
                answers_json={},
            )
            session.add_all([fixed, task, goal])
            session.commit()
            token = create_access_token(requester.id)
            fixed_id = fixed.id
            task_id = task.id
            goal_id = goal.id

        headers = {"Authorization": f"Bearer {token}"}

        assert client.get(f"/api/v1/schedules/fixed/{fixed_id}", headers=headers).status_code == 404
        assert client.patch(
            f"/api/v1/tasks/flexible/{task_id}",
            headers=headers,
            json={"title": "Leaked update"},
        ).status_code == 404
        assert client.delete(f"/api/v1/goals/{goal_id}", headers=headers).status_code == 404

        with session_local() as session:
            assert session.get(FixedSchedule, fixed_id).title == "Private class"
            assert session.get(FlexibleTask, task_id).title == "Private task"
            assert session.get(Goal, goal_id) is not None
    finally:
        app.dependency_overrides.clear()


def test_plan_item_schedule_mutations_require_token_owner():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            requester = _create_user(session, "plan-requester@example.com")
            owner = _create_user(session, "plan-owner@example.com")
            goal = Goal(
                user_id=owner.id,
                title="Private plan goal",
                category=GoalCategory.work,
                status=GoalStatus.active,
                details_json={},
                answers_json={},
            )
            session.add(goal)
            session.flush()
            plan = AIPlan(
                user_id=owner.id,
                goal_id=goal.id,
                summary="Private plan",
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
                user_id=owner.id,
                title="Private item",
                item_type="work",
                estimated_minutes=60,
                priority=2,
                is_schedulable=True,
                scheduled_start=datetime(2026, 5, 19, 9),
                scheduled_end=datetime(2026, 5, 19, 10),
                status=PlanItemStatus.scheduled,
                metadata_json={},
            )
            session.add(item)
            session.commit()
            token = create_access_token(requester.id)
            item_id = item.id

        headers = {"Authorization": f"Bearer {token}"}

        assert client.delete(f"/api/v1/planner/plan-items/{item_id}/schedule", headers=headers).status_code == 404
        assert client.post(f"/api/v1/planner/plan-items/{item_id}/skip", headers=headers).status_code == 404

        with session_local() as session:
            item = session.get(AIPlanItem, item_id)
            assert item.status == PlanItemStatus.scheduled
            assert item.scheduled_start == datetime(2026, 5, 19, 9)
            assert item.scheduled_end == datetime(2026, 5, 19, 10)
    finally:
        app.dependency_overrides.clear()
