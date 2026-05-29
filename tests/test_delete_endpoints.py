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


def _create_user(session: Session, email: str = "delete@example.com") -> User:
    user = User(
        email=email,
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


def test_delete_flexible_task_removes_calendar_allocations():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="delete-flexible-task@example.com")
            task = FlexibleTask(
                user_id=user.id,
                title="Original variable task",
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

        before_response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 5, 1, 8).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert before_response.status_code == 200
        assert before_response.json()["events"][0]["metadata_json"]["flexible_task_id"] == task_id

        delete_response = client.delete(
            f"/api/v1/tasks/flexible/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_response.status_code == 200

        after_response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 5, 1, 8).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert after_response.status_code == 200
        assert after_response.json()["events"] == []

        with session_local() as session:
            assert session.get(FlexibleTask, task_id) is None
            assert session.get(AllocatedTask, allocation_id) is None
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


def test_delete_plan_item_removes_calendar_event_but_keeps_goal_and_plan():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="delete-plan-item@example.com")
            goal = Goal(
                user_id=user.id,
                title="Old goal",
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
                summary="Old plan",
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
                title="Old analyzed item",
                item_type="work",
                estimated_minutes=60,
                priority=2,
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

        before_response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 5, 1, 8).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert before_response.status_code == 200
        assert [event["source_id"] for event in before_response.json()["events"]] == [item_id]

        delete_response = client.delete(
            f"/api/v1/planner/plan-items/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["detail"] == "Plan item deleted."

        after_response = client.get(
            "/api/v1/calendar",
            params={
                "start": datetime(2026, 5, 1, 8).isoformat(),
                "end": datetime(2026, 5, 1, 11).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert after_response.status_code == 200
        assert after_response.json()["events"] == []

        with session_local() as session:
            assert session.get(Goal, goal_id) is not None
            assert session.get(AIPlan, plan_id) is not None
            assert session.get(AIPlanItem, item_id) is None
    finally:
        app.dependency_overrides.clear()


def test_goal_clear_schedule_only_unschedules_that_goal():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="goal-clear@example.com")
            goals = [
                Goal(
                    user_id=user.id,
                    title="Goal A",
                    category=GoalCategory.work,
                    status=GoalStatus.active,
                    details_json={},
                    answers_json={},
                ),
                Goal(
                    user_id=user.id,
                    title="Goal B",
                    category=GoalCategory.work,
                    status=GoalStatus.active,
                    details_json={},
                    answers_json={},
                ),
            ]
            session.add_all(goals)
            session.flush()
            plans = [
                AIPlan(
                    user_id=user.id,
                    goal_id=goal.id,
                    summary=goal.title,
                    strategy_json={},
                    recommendations_json={},
                    raw_plan_json={},
                    llm_mode="template-fallback",
                    status=PlanStatus.active,
                )
                for goal in goals
            ]
            session.add_all(plans)
            session.flush()
            items = [
                AIPlanItem(
                    ai_plan_id=plans[0].id,
                    goal_id=goals[0].id,
                    user_id=user.id,
                    title="Goal A item",
                    item_type="work",
                    estimated_minutes=60,
                    priority=2,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 5, 1, 9),
                    scheduled_end=datetime(2026, 5, 1, 10),
                    status=PlanItemStatus.scheduled,
                    metadata_json={},
                ),
                AIPlanItem(
                    ai_plan_id=plans[1].id,
                    goal_id=goals[1].id,
                    user_id=user.id,
                    title="Goal B item",
                    item_type="work",
                    estimated_minutes=60,
                    priority=2,
                    is_schedulable=True,
                    scheduled_start=datetime(2026, 5, 1, 10),
                    scheduled_end=datetime(2026, 5, 1, 11),
                    status=PlanItemStatus.scheduled,
                    metadata_json={},
                ),
            ]
            session.add_all(items)
            session.commit()
            token = create_access_token(user.id)
            goal_id = goals[0].id
            item_ids = [item.id for item in items]

        response = client.post(
            f"/api/v1/goals/{goal_id}/clear-schedule",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        with session_local() as session:
            cleared_item = session.get(AIPlanItem, item_ids[0])
            other_item = session.get(AIPlanItem, item_ids[1])
            assert cleared_item.status == PlanItemStatus.suggested
            assert cleared_item.scheduled_start is None
            assert cleared_item.scheduled_end is None
            assert other_item.status == PlanItemStatus.scheduled
            assert other_item.scheduled_start == datetime(2026, 5, 1, 10)
    finally:
        app.dependency_overrides.clear()


def test_goal_allocate_only_schedules_requested_goal():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session, email="goal-allocate@example.com")
            goals = [
                Goal(
                    user_id=user.id,
                    title="Goal A",
                    category=GoalCategory.work,
                    status=GoalStatus.active,
                    details_json={},
                    answers_json={},
                ),
                Goal(
                    user_id=user.id,
                    title="Goal B",
                    category=GoalCategory.work,
                    status=GoalStatus.active,
                    details_json={},
                    answers_json={},
                ),
            ]
            session.add_all(goals)
            session.flush()
            plans = [
                AIPlan(
                    user_id=user.id,
                    goal_id=goal.id,
                    summary=goal.title,
                    strategy_json={},
                    recommendations_json={},
                    raw_plan_json={},
                    llm_mode="template-fallback",
                    status=PlanStatus.active,
                )
                for goal in goals
            ]
            session.add_all(plans)
            session.flush()
            items = [
                AIPlanItem(
                    ai_plan_id=plans[0].id,
                    goal_id=goals[0].id,
                    user_id=user.id,
                    title="Goal A item",
                    item_type="work",
                    estimated_minutes=60,
                    priority=2,
                    target_date=date(2026, 5, 1),
                    is_schedulable=True,
                    status=PlanItemStatus.suggested,
                    metadata_json={},
                ),
                AIPlanItem(
                    ai_plan_id=plans[1].id,
                    goal_id=goals[1].id,
                    user_id=user.id,
                    title="Goal B item",
                    item_type="work",
                    estimated_minutes=60,
                    priority=2,
                    target_date=date(2026, 5, 1),
                    is_schedulable=True,
                    status=PlanItemStatus.suggested,
                    metadata_json={},
                ),
            ]
            session.add_all(items)
            session.commit()
            token = create_access_token(user.id)
            goal_id = goals[0].id
            item_ids = [item.id for item in items]

        response = client.post(
            f"/api/v1/goals/{goal_id}/allocate",
            json={
                "range_start": datetime(2026, 5, 1, 9).isoformat(),
                "range_end": datetime(2026, 5, 1, 18).isoformat(),
                "buffer_minutes": 0,
                "clear_existing": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["allocated_tasks"] == []
        assert [item["title"] for item in response.json()["scheduled_plan_items"]] == ["Goal A item"]

        with session_local() as session:
            scheduled_item = session.get(AIPlanItem, item_ids[0])
            untouched_item = session.get(AIPlanItem, item_ids[1])
            assert scheduled_item.status == PlanItemStatus.scheduled
            assert scheduled_item.scheduled_start is not None
            assert untouched_item.status == PlanItemStatus.suggested
            assert untouched_item.scheduled_start is None
    finally:
        app.dependency_overrides.clear()
