from backend.models.enums import GoalCategory
from backend.schemas.planning import GoalIntakeRequest
from backend.services.planning import PlanningService


def test_goal_intake_questions_are_korean_and_schedule_oriented(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(
            text="캡스톤 발표를 2026년 5월 20일까지 준비하고 주당 8시간 정도 가능해요.",
            category=GoalCategory.work,
        )
    )

    questions = {question.key: question for question in response.questions}

    assert [question.key for question in response.questions[:6]] == [
        "target_date",
        "weekly_available_hours",
        "preferred_work_times",
        "unavailable_times",
        "session_preference",
        "constraints",
    ]
    assert questions["target_date"].prompt == "언제까지 완료해야 하나요?"
    assert questions["preferred_work_times"].required is False
    assert questions["session_preference"].answer_type == "select"
    assert "보통 길이로 균형 있게" in questions["session_preference"].options
    assert questions["current_progress"].prompt == "현재 어디까지 진행되어 있나요?"
    assert all("What " not in question.prompt for question in response.questions)
