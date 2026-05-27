from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.routes import auth as auth_route
from backend.api.routes import calendar as calendar_route
from backend.core.auth import create_access_token
from backend.db.session import get_db_session
from backend.main import app
from backend.models.ai_plan import AIPlan
from backend.models.allocated_task import AllocatedTask
from backend.models.base import Base
from backend.models.enums import FlexibleTaskStatus, GoalCategory, GoalStatus, PlanStatus
from backend.models.fixed_schedule import FixedSchedule
from backend.models.flexible_task import FlexibleTask
from backend.models.goal import Goal
from backend.models.user import User
from backend.schemas.planning import GoalCompleteRequest


def _client_with_session(*, raise_server_exceptions: bool = True):
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
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), session_local


def _create_user(session: Session, *, email: str) -> User:
    user = User(
        email=email,
        name="API User",
        hashed_password="x",
        timezone="Asia/Seoul",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_user_lookup_routes_require_auth_and_only_return_self():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            first_user = _create_user(session, email="first@example.com")
            second_user = _create_user(session, email="second@example.com")
            token = create_access_token(first_user.id)

        assert client.get("/api/v1/users").status_code == 401
        assert client.get(f"/api/v1/users/{first_user.id}").status_code == 401

        list_response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [first_user.id]

        own_response = client.get(
            f"/api/v1/users/{first_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert own_response.status_code == 200
        assert own_response.json()["email"] == "first@example.com"

        other_response = client.get(
            f"/api/v1/users/{second_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert other_response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_goal_intake_requires_authentication():
    client, session_local = _client_with_session()
    try:
        response = client.post(
            "/api/v1/goals/intake",
            json={"text": "toeic 850 by 2026-08-31", "category": "study"},
        )
        assert response.status_code == 401

        with session_local() as session:
            user = _create_user(session, email="intake@example.com")
            token = create_access_token(user.id)

        authenticated_response = client.post(
            "/api/v1/goals/intake",
            json={"text": "toeic 850 by 2026-08-31", "category": "study"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert authenticated_response.status_code == 200
        assert authenticated_response.json()["goal"]["category"] == "study"
    finally:
        app.dependency_overrides.clear()


def test_complete_goal_rolls_back_goal_when_plan_generation_fails():
    from backend.api.routes import goals as goals_route

    client, session_local = _client_with_session(raise_server_exceptions=False)
    original_service = goals_route.planning_service

    class FailingPlanningService:
        def parse_goal_input(self, payload):
            return original_service.parse_goal_input(payload)

        def build_plan(self, goal, answers):
            raise RuntimeError("forced plan failure")

    try:
        with session_local() as session:
            user = _create_user(session, email="complete-failure@example.com")
            token = create_access_token(user.id)

        goals_route.planning_service = FailingPlanningService()
        response = client.post(
            "/api/v1/goals/complete",
            json={"text": "toeic 850 by 2026-08-31", "category": "study"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Goal plan generation failed."
        with session_local() as session:
            assert session.query(Goal).count() == 0
    finally:
        goals_route.planning_service = original_service
        app.dependency_overrides.clear()


def test_complete_goal_persists_goal_and_plan_items():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="complete-success@example.com")
            token = create_access_token(user.id)

        response = client.post(
            "/api/v1/goals/complete",
            json={
                "text": "toeic 850 by 2026-08-31",
                "category": "study",
                "answers_json": {"weekly_available_hours": 6},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["goal"]["status"] == "active"
        assert body["plan"]["goal_id"] == body["goal"]["id"]
        assert body["plan"]["items"]

        with session_local() as session:
            assert session.query(Goal).count() == 1
    finally:
        app.dependency_overrides.clear()


def test_goal_complete_replace_existing_defaults_to_false():
    payload = GoalCompleteRequest(text="prepare a demo")

    assert payload.replace_existing is False


def test_complete_goal_replace_existing_does_not_archive_other_goal_plans():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="replace-existing@example.com")
            other_user = _create_user(session, email="replace-existing-other@example.com")
            old_goal = Goal(
                user_id=user.id,
                title="Old goal",
                category=GoalCategory.work,
                status=GoalStatus.active,
                details_json={},
                answers_json={},
            )
            other_goal = Goal(
                user_id=other_user.id,
                title="Other goal",
                category=GoalCategory.work,
                status=GoalStatus.active,
                details_json={},
                answers_json={},
            )
            session.add_all([old_goal, other_goal])
            session.flush()
            old_plan = AIPlan(
                user_id=user.id,
                goal_id=old_goal.id,
                summary="old",
                strategy_json={},
                recommendations_json={},
                raw_plan_json={},
                llm_mode="template-fallback",
                status=PlanStatus.active,
            )
            other_plan = AIPlan(
                user_id=other_user.id,
                goal_id=other_goal.id,
                summary="other",
                strategy_json={},
                recommendations_json={},
                raw_plan_json={},
                llm_mode="template-fallback",
                status=PlanStatus.active,
            )
            session.add_all([old_plan, other_plan])
            session.commit()
            token = create_access_token(user.id)
            old_plan_id = old_plan.id
            other_plan_id = other_plan.id

        response = client.post(
            "/api/v1/goals/complete",
            json={
                "text": "prepare a demo by 2026-08-31",
                "category": "work",
                "answers_json": {"weekly_available_hours": 3},
                "replace_existing": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        new_plan_id = response.json()["plan"]["id"]
        with session_local() as session:
            assert session.get(AIPlan, old_plan_id).status == PlanStatus.active
            assert session.get(AIPlan, new_plan_id).status == PlanStatus.active
            assert session.get(AIPlan, other_plan_id).status == PlanStatus.active
    finally:
        app.dependency_overrides.clear()


def test_google_login_rejects_claims_without_provider_subject(monkeypatch):
    client, session_local = _client_with_session()

    def missing_subject_claims(credential: str):
        return {"email": "google@example.com", "email_verified": True, "name": "Google User"}

    monkeypatch.setattr(auth_route, "_verify_google_credential", missing_subject_claims)
    try:
        response = client.post("/api/v1/auth/google", json={"credential": "token"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid Google credential."
        with session_local() as session:
            assert session.query(User).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_google_login_requires_verified_email_claim(monkeypatch):
    client, session_local = _client_with_session()

    def unverified_claims(credential: str):
        return {"sub": "google-user-id", "email": "google@example.com", "name": "Google User"}

    monkeypatch.setattr(auth_route, "_verify_google_credential", unverified_claims)
    try:
        response = client.post("/api/v1/auth/google", json={"credential": "token"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Google email is not verified."
        with session_local() as session:
            assert session.query(User).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_calendar_service_failure_returns_500_instead_of_empty_calendar():
    client, session_local = _client_with_session()
    original_build = calendar_route.calendar_service.build
    try:
        with session_local() as session:
            user = _create_user(session, email="calendar@example.com")
            token = create_access_token(user.id)

        def fail_build(*args, **kwargs):
            raise RuntimeError("forced calendar failure")

        calendar_route.calendar_service.build = fail_build

        response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 5, 1).isoformat(),
                "end": datetime(2026, 5, 2).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "Calendar generation failed."
    finally:
        calendar_route.calendar_service.build = original_build
        app.dependency_overrides.clear()


def test_fixed_schedule_list_rejects_invalid_or_unbounded_ranges():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="schedule-range@example.com")
            token = create_access_token(user.id)

        reversed_response = client.get(
            "/api/v1/schedules/fixed",
            params={
                "start": datetime(2026, 5, 2).isoformat(),
                "end": datetime(2026, 5, 1).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reversed_response.status_code == 400

        unbounded_response = client.get(
            "/api/v1/schedules/fixed",
            params={
                "start": datetime(2026, 1, 1).isoformat(),
                "end": datetime(2028, 1, 1).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert unbounded_response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_fixed_schedule_list_uses_strict_overlap_boundaries():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="schedule-overlap@example.com")
            token = create_access_token(user.id)

        create_response = client.post(
            "/api/v1/schedules/fixed",
            json={
                "title": "Exact boundary class",
                "start_at": datetime(2026, 5, 1, 9).isoformat(),
                "end_at": datetime(2026, 5, 1, 10).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_response.status_code == 201
        schedule_id = create_response.json()["id"]

        after_response = client.get(
            "/api/v1/schedules/fixed",
            params={
                "start": datetime(2026, 5, 1, 10).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert after_response.status_code == 200
        assert after_response.json() == []

        before_response = client.get(
            "/api/v1/schedules/fixed",
            params={
                "start": datetime(2026, 5, 1, 8).isoformat(),
                "end": datetime(2026, 5, 1, 9).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert before_response.status_code == 200
        assert before_response.json() == []

        overlap_response = client.get(
            "/api/v1/schedules/fixed",
            params={
                "start": datetime(2026, 5, 1, 9, 30).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert overlap_response.status_code == 200
        assert [item["id"] for item in overlap_response.json()] == [schedule_id]

        with session_local() as session:
            assert session.get(FixedSchedule, schedule_id) is not None
    finally:
        app.dependency_overrides.clear()


def test_cancelling_flexible_task_removes_existing_allocations_from_calendar():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="cancel-flexible@example.com")
            task = FlexibleTask(
                user_id=user.id,
                title="Cancelled task",
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
            task_id = task.id
            allocation_id = allocation.id

        patch_response = client.patch(
            f"/api/v1/tasks/flexible/{task_id}",
            json={"status": "cancelled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["status"] == "cancelled"
        assert patch_response.json()["allocated_minutes"] == 0

        calendar_response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 5, 1, 8).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert calendar_response.status_code == 200
        assert calendar_response.json()["events"] == []

        with session_local() as session:
            assert session.get(AllocatedTask, allocation_id) is None
            assert session.get(FlexibleTask, task_id).status == FlexibleTaskStatus.cancelled
    finally:
        app.dependency_overrides.clear()


def test_calendar_and_planner_reject_unbounded_ranges():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="range@example.com")
            token = create_access_token(user.id)

        calendar_response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 1, 1).isoformat(),
                "end": datetime(2028, 1, 1).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert calendar_response.status_code == 400

        planner_response = client.post(
            "/api/v1/planner/allocate",
            json={
                "range_start": datetime(2026, 1, 1).isoformat(),
                "range_end": datetime(2026, 6, 1).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert planner_response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_flexible_task_priority_accepts_frontend_default_scale():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="priority@example.com")
            token = create_access_token(user.id)

        response = client.post(
            "/api/v1/tasks/flexible",
            json={
                "title": "UI default priority task",
                "estimated_minutes": 60,
                "min_session_minutes": 15,
                "preferred_session_minutes": 30,
                "max_minutes_per_day": 60,
                "priority": 5,
                "details_json": {},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["priority"] == 5

        with session_local() as session:
            task = session.get(FlexibleTask, response.json()["id"])
            assert task is not None
            assert task.priority == 5
    finally:
        app.dependency_overrides.clear()
