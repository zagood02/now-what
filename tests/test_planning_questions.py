from datetime import date

from backend.models.enums import GoalCategory
from backend.models.goal import Goal
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


def test_toeic_keyword_routes_to_domain_questions_and_prefills(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(
            text="토익 850점을 2026년 8월 31일까지 만들고 싶고 주당 7시간 가능해요.",
        )
    )

    question_keys = [question.key for question in response.questions]

    assert response.goal.category == GoalCategory.study
    assert response.goal.title == "토익 850점"
    assert response.goal.details_json["study_subtype"] == "study.toeic"
    assert response.goal.details_json["study_subtype_source"] == "keyword"
    assert response.goal.answers_json["target_date"] == "2026-08-31"
    assert response.goal.answers_json["weekly_available_hours"] == 7
    assert response.goal.answers_json["target_score"] == 850
    assert "current_score" in question_keys
    assert "target_score" in question_keys
    assert "weak_sections" in question_keys
    assert "practice_test_access" in question_keys


def test_toeic_speaking_does_not_route_to_toeic_template(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(text="토익스피킹 준비하고 싶어요.")
    )

    assert response.goal.category == GoalCategory.study
    assert "study_subtype" not in response.goal.details_json
    assert response.goal.title == "토익스피킹"


def test_study_goal_title_and_item_titles_stay_calendar_friendly(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(text="토익 850점 목표입니다.")
    )
    goal = Goal(
        user_id=1,
        title=response.goal.title,
        description=response.goal.description,
        category=response.goal.category,
        target_date=date(2026, 8, 31),
        details_json=response.goal.details_json,
        answers_json=response.goal.answers_json,
    )

    draft = service.build_plan(goal, response.goal.answers_json)

    assert response.goal.title == "토익 850점"
    assert draft.items[0].title == "토익 진단 세트와 목표 점수 갭 분석"
    assert all(" - " not in item.title for item in draft.items)


def test_study_goal_title_can_use_answers_provided_after_intake(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(text="토익 준비하고 싶어요.")
    )

    title = service.refine_goal_title(
        response.goal.title,
        response.goal.details_json,
        {"target_score": 850},
    )

    assert response.goal.title == "토익"
    assert title == "토익 850점"


def test_toeic_template_plan_contains_quality_loop(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")
    goal = Goal(
        user_id=1,
        title="토익 850점",
        description="토익 점수를 올리고 싶어요.",
        category=GoalCategory.study,
        target_date=date(2026, 8, 31),
        details_json={"study_subtype": "study.toeic"},
        answers_json={},
    )

    draft = service.build_plan(
        goal,
        {
            "weekly_available_hours": 7,
            "target_score": 850,
            "weak_sections": "RC",
            "materials": "해커스 토익 1000제, 노랭이 단어장",
        },
    )

    item_types = {item.item_type for item in draft.items}
    sections = {item.metadata_json.get("section") for item in draft.items}

    assert draft.strategy_json["study_subtype"] == "study.toeic"
    assert draft.raw_plan_json["quality_validation"]["passed"] is True
    assert {"diagnostic", "vocabulary", "lc_practice", "rc_practice", "mock_test", "mistake_review", "final_review"}.issubset(item_types)
    assert {"LC", "RC"}.issubset(sections)
    assert draft.strategy_json["user_materials"] == "해커스 토익 1000제, 노랭이 단어장"
    assert draft.recommendations_json["materials"][0] == "사용자 지정 자료: 해커스 토익 1000제, 노랭이 단어장"
    assert "해커스 토익 1000제" in draft.items[0].description
    assert draft.items[0].metadata_json["materials"] == "해커스 토익 1000제, 노랭이 단어장"
    assert draft.llm_mode == "template-fallback-study-toeic"


def test_information_processing_engineer_keyword_routes_and_plan_validates(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(
            text="정보처리기사 실기를 2026년 7월 20일까지 준비하고 주당 6시간 공부할 수 있어요.",
        )
    )
    question_keys = [question.key for question in response.questions]

    assert response.goal.category == GoalCategory.study
    assert response.goal.title == "정보처리기사 실기"
    assert response.goal.details_json["study_subtype"] == "study.cert.information_processing_engineer"
    assert response.goal.answers_json["exam_stage"] == "실기"
    assert "exam_stage" in question_keys
    assert "weak_subjects" in question_keys

    goal = Goal(
        user_id=1,
        title="정보처리기사 실기",
        description="정보처리기사 실기를 준비합니다.",
        category=GoalCategory.study,
        target_date=date(2026, 7, 20),
        details_json=response.goal.details_json,
        answers_json=response.goal.answers_json,
    )
    draft = service.build_plan(goal, response.goal.answers_json)
    item_types = {item.item_type for item in draft.items}

    assert draft.strategy_json["study_subtype"] == "study.cert.information_processing_engineer"
    assert draft.raw_plan_json["quality_validation"]["passed"] is True
    assert {"diagnostic", "past_exam", "mistake_review", "practical_drill", "mock_test", "final_review"}.issubset(item_types)
