from datetime import date, timedelta
import json

import pytest

from backend.models.enums import GoalCategory
from backend.models.goal import Goal
from backend.schemas.planning import GoalIntakeRequest
from backend.services.planning import InvalidGoalInputError, PlanDraftItem, PlanningService


def test_goal_intake_questions_are_korean_and_schedule_oriented(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(
            text="캡스톤 발표를 2026년 5월 20일까지 준비하고 주당 8시간 정도 가능해요.",
            category=GoalCategory.work,
        )
    )

    question_keys = [question.key for question in response.questions]
    questions = {question.key: question for question in response.questions}

    assert len(question_keys) == len(set(question_keys))
    assert question_keys[:6] == [
        "target_date",
        "weekly_available_hours",
        "session_preference",
        "constraints",
        "current_progress",
        "deliverables",
    ]
    required_keys = {question.key for question in response.questions if question.required}

    assert required_keys == {
        "target_date",
        "weekly_available_hours",
        "current_progress",
        "deliverables",
        "success_definition",
    }
    assert questions["target_date"].prompt == "이 목표를 언제까지 완료하거나 1차 점검해야 하나요?"
    assert questions["session_preference"].answer_type == "select"
    assert "보통 길이 60-90분" in questions["session_preference"].options
    assert questions["current_progress"].prompt == "현재 완료된 부분과 아직 남은 부분은 어디까지인가요?"
    assert questions["dependencies"].required is False
    assert all("What " not in question.prompt for question in response.questions)


def test_gemini_invalid_goal_flag_stops_template_fallback(monkeypatch):
    class FakeResponse:
        text = json.dumps(
            {
                "is_goal_like": False,
                "clarification_message": "Please enter a clearer goal.",
                "title": "",
                "description": None,
                "inferred_category": "general",
                "reasoning": "Input is too vague to plan.",
                "details_json": {},
                "suggested_answers_json": {},
            }
        )

    class FakeModels:
        def generate_content(self, **_kwargs):
            return FakeResponse()

    class FakeClient:
        models = FakeModels()

    service = PlanningService(client=FakeClient())
    monkeypatch.setattr(service, "_can_use_gemini", lambda: True)

    with pytest.raises(InvalidGoalInputError) as exc_info:
        service.parse_goal_input(GoalIntakeRequest(text="I want to maybe do the thing"))

    assert "clearer goal" in exc_info.value.detail


def test_category_questions_have_domain_specific_required_and_optional_fields(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    cases = {
        GoalCategory.health: (
            {"current_state", "target_metric", "activity_capacity"},
            {"recovery_limits", "diet_constraints"},
        ),
        GoalCategory.habit: (
            {"current_pattern", "desired_frequency", "trigger", "obstacles"},
            {"accountability"},
        ),
        GoalCategory.general: (
            {"current_state", "success_definition", "priority_scope"},
            {"first_milestone", "risks"},
        ),
    }

    for category, (required_domain_keys, optional_domain_keys) in cases.items():
        response = service.parse_goal_input(GoalIntakeRequest(text="새 목표를 정리하고 싶어요.", category=category))
        questions = {question.key: question for question in response.questions}
        question_keys = [question.key for question in response.questions]

        assert len(question_keys) == len(set(question_keys))
        assert required_domain_keys.issubset({key for key, question in questions.items() if question.required})
        assert optional_domain_keys.issubset({key for key, question in questions.items() if not question.required})


def test_toeic_keyword_routes_to_domain_questions_and_prefills(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(
            text="토익 850점을 2026년 8월 31일까지 만들고 싶고 주당 7시간 가능해요.",
        )
    )

    question_keys = [question.key for question in response.questions]
    questions = {question.key: question for question in response.questions}

    assert response.goal.category == GoalCategory.study
    assert response.goal.details_json["study_subtype"] == "study.toeic"
    assert response.goal.details_json["study_subtype_source"] == "keyword"
    assert response.goal.answers_json["target_date"] == "2026-08-31"
    assert response.goal.answers_json["weekly_available_hours"] == 7
    assert response.goal.answers_json["target_score"] == 850
    assert "current_score" in question_keys
    assert "target_score" in question_keys
    assert "weak_sections" in question_keys
    assert "practice_test_access" in question_keys
    assert "vocabulary_routine" in question_keys
    assert questions["target_score"].required is True
    assert questions["current_score"].required is False
    assert questions["weak_sections"].required is False


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
    assert all(item.estimated_minutes <= service.MAX_PLAN_ITEM_SESSION_MINUTES for item in draft.items)


def test_plan_minutes_scale_by_weekly_hours_across_goal_horizon(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")
    target_date = date.today() + timedelta(days=20)
    goal = Goal(
        user_id=1,
        title="Demo presentation",
        description="Prepare a capstone presentation.",
        category=GoalCategory.work,
        target_date=None,
        details_json={},
        answers_json={},
    )

    draft = service.build_plan(
        goal,
        {
            "weekly_available_hours": "4",
            "target_date": target_date.isoformat(),
        },
    )

    total_minutes = sum(item.estimated_minutes for item in draft.items if item.is_schedulable)

    assert draft.strategy_json["weekly_hours"] == 4
    assert draft.strategy_json["planning_horizon_weeks"] == 3
    assert draft.strategy_json["target_total_minutes"] == 720
    assert total_minutes >= draft.strategy_json["target_total_minutes"]
    assert draft.items[-1].target_date == target_date


def test_target_minutes_are_prorated_for_partial_weeks():
    service = PlanningService()
    target_date = date.today() + timedelta(days=9)

    assert service._planning_horizon_days(target_date) == 10
    assert service._planning_horizon_weeks(target_date) == 2
    assert service._target_total_minutes(4, target_date) == 360


def test_plan_scaling_repeats_work_blocks_not_one_time_setup(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")
    target_date = date.today() + timedelta(days=20)
    goal = Goal(
        user_id=1,
        title="TOEIC 850",
        description="Prepare TOEIC score.",
        category=GoalCategory.study,
        target_date=target_date,
        details_json={"study_subtype": "study.toeic"},
        answers_json={},
    )

    draft = service.build_plan(
        goal,
        {
            "weekly_available_hours": 8,
            "target_score": 850,
        },
    )

    item_types = [item.item_type for item in draft.items]

    assert draft.strategy_json["target_total_minutes"] == 1440
    assert sum(item.estimated_minutes for item in draft.items if item.is_schedulable) >= 1440
    assert item_types.count("diagnostic") == 1
    assert item_types.count("final_review") == 1
    assert any(item.metadata_json.get("repeat_number") for item in draft.items)


def test_long_plan_items_are_split_into_schedulable_chunks():
    service = PlanningService()
    item = PlanDraftItem(
        title="긴 조사와 정리 작업",
        description="한 번에 끝내기 어려운 긴 작업입니다.",
        item_type="deep_work",
        estimated_minutes=300,
        priority=3,
        target_date=date(2026, 8, 31),
        metadata_json={"source": "test"},
    )

    chunks = service._split_plan_items_for_scheduling([item])

    assert [chunk.estimated_minutes for chunk in chunks] == [100, 100, 100]
    assert [chunk.metadata_json["split_part"] for chunk in chunks] == [1, 2, 3]
    assert all(chunk.estimated_minutes <= service.MAX_PLAN_ITEM_SESSION_MINUTES for chunk in chunks)
    assert chunks[0].title == "긴 조사와 정리 작업 (1/3)"


def test_split_item_titles_and_descriptions_do_not_accumulate_labels():
    service = PlanningService()

    assert service._split_minutes(100, 45) == [35, 35, 30]
    assert service._split_item_title("Deep work (1/2)", 1, 3) == "Deep work (1/3)"
    assert (
        service._split_item_description("Base description\n\n분할된 일정 1/2입니다.", 1, 3)
        == "Base description"
    )


def test_weekly_hours_are_clamped_to_realistic_bounds():
    service = PlanningService()

    assert (
        service._resolve_weekly_hours({"weekly_available_hours": 999})
        == service.MAX_WEEKLY_AVAILABLE_HOURS
    )
    assert (
        service._resolve_weekly_hours(
            {"daily_available_minutes": 1440, "study_days_per_week": 10}
        )
        == service.MAX_WEEKLY_AVAILABLE_HOURS
    )
    assert service._resolve_weekly_hours({"weekly_available_hours": 0}) == 6


def test_target_minutes_are_capped_to_generated_item_capacity():
    service = PlanningService()
    target_date = date.today() + timedelta(days=365)
    items = [
        PlanDraftItem(
            title="Small repeatable block",
            description="Repeat this block.",
            item_type="practice",
            estimated_minutes=30,
            priority=3,
            target_date=target_date,
            metadata_json={},
        )
    ]

    target_total_minutes = service._target_total_minutes_for_items(
        service.MAX_WEEKLY_AVAILABLE_HOURS,
        target_date,
        items,
    )
    expanded = service._scale_items_to_planning_horizon(
        items,
        service.MAX_WEEKLY_AVAILABLE_HOURS,
        target_date,
        target_total_minutes=target_total_minutes,
    )
    actual_total_minutes = sum(
        item.estimated_minutes for item in expanded if item.is_schedulable
    )

    assert target_total_minutes == service.MAX_GENERATED_PLAN_ITEMS * 30
    assert len(expanded) == service.MAX_GENERATED_PLAN_ITEMS
    assert actual_total_minutes >= target_total_minutes


def test_information_processing_engineer_keyword_routes_and_plan_validates(monkeypatch):
    service = PlanningService()
    monkeypatch.setattr(service.settings, "llm_model", "template-fallback")

    response = service.parse_goal_input(
        GoalIntakeRequest(
            text="정보처리기사 실기를 2026년 7월 20일까지 준비하고 주당 6시간 공부할 수 있어요.",
        )
    )
    question_keys = [question.key for question in response.questions]
    questions = {question.key: question for question in response.questions}

    assert response.goal.category == GoalCategory.study
    assert response.goal.details_json["study_subtype"] == "study.cert.information_processing_engineer"
    assert response.goal.answers_json["exam_stage"] == "실기"
    assert "exam_stage" in question_keys
    assert "weak_subjects" in question_keys
    assert "practical_drill_format" in question_keys
    assert questions["exam_stage"].required is True
    assert questions["weak_subjects"].required is False
    assert questions["practical_drill_format"].required is False

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
