from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.auth import create_access_token
from backend.db.session import get_db_session
from backend.main import app
from backend.models.base import Base
from backend.models.fixed_schedule import FixedSchedule
from backend.models.user import User
from backend.services.recurrence import expand_fixed_schedule, normalize_recurrence_rule


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
        email="fixed-schedule@example.com",
        name="Fixed Schedule User",
        hashed_password="x",
        timezone="Asia/Seoul",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_weekly_and_biweekly_require_day_of_week():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session)
            token = create_access_token(user.id)

        response = client.post(
            "/api/v1/schedules/fixed",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Team meeting",
                "start_at": "2026-04-14T14:00:00+09:00",
                "end_at": "2026-04-14T15:00:00+09:00",
                "recurrence_rule": "weekly",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "weekly 및 biweekly 반복은 요일 선택이 필요합니다."
    finally:
        app.dependency_overrides.clear()


def test_weekly_schedule_accepts_day_of_week():
    client, session_local = _client_with_session()
    try:
        with session_local() as session:
            user = _create_user(session)
            token = create_access_token(user.id)

        response = client.post(
            "/api/v1/schedules/fixed",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Team meeting",
                "start_at": "2026-04-14T14:00:00+09:00",
                "end_at": "2026-04-14T15:00:00+09:00",
                "recurrence_rule": "weekly",
                "day_of_week": 2,
            },
        )

        assert response.status_code == 201
        assert response.json()["recurrence_rule"] == "weekly"
        assert response.json()["day_of_week"] == 2
    finally:
        app.dependency_overrides.clear()


def test_weekly_and_biweekly_expand_from_selected_weekday():
    weekly = FixedSchedule(
        user_id=1,
        title="Weekly meeting",
        start_at=datetime(2026, 4, 13, 14),
        end_at=datetime(2026, 4, 13, 15),
        recurrence_rule="weekly",
        day_of_week=2,
        is_all_day=False,
    )
    biweekly = FixedSchedule(
        user_id=1,
        title="Biweekly meeting",
        start_at=datetime(2026, 4, 13, 14),
        end_at=datetime(2026, 4, 13, 15),
        recurrence_rule="biweekly",
        day_of_week=2,
        is_all_day=False,
    )

    weekly_occurrences = expand_fixed_schedule(
        weekly,
        range_start=datetime(2026, 4, 14),
        range_end=datetime(2026, 4, 29),
    )
    biweekly_occurrences = expand_fixed_schedule(
        biweekly,
        range_start=datetime(2026, 4, 14),
        range_end=datetime(2026, 5, 6),
    )

    assert [item.start_at for item in weekly_occurrences] == [
        datetime(2026, 4, 14, 14),
        datetime(2026, 4, 21, 14),
        datetime(2026, 4, 28, 14),
    ]
    assert [item.start_at for item in biweekly_occurrences] == [
        datetime(2026, 4, 14, 14),
        datetime(2026, 4, 28, 14),
    ]


def test_monthly_schedule_expands_on_same_day_with_month_end_clamp():
    schedule = FixedSchedule(
        user_id=1,
        title="Monthly review",
        start_at=datetime(2026, 1, 31, 14),
        end_at=datetime(2026, 1, 31, 15),
        recurrence_rule="monthly",
        is_all_day=False,
    )

    occurrences = expand_fixed_schedule(
        schedule,
        range_start=datetime(2026, 1, 1),
        range_end=datetime(2026, 4, 1),
    )

    assert [item.start_at for item in occurrences] == [
        datetime(2026, 1, 31, 14),
        datetime(2026, 2, 28, 14),
        datetime(2026, 3, 31, 14),
    ]


def test_korean_recurrence_aliases_match_backend_template():
    assert normalize_recurrence_rule("매주") == "weekly"
    assert normalize_recurrence_rule("격주") == "biweekly"
