from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.core.config import settings
from backend.models.enums import GoalCategory
from backend.models.goal import Goal
from backend.schemas.planning import (
    GoalDraftSuggestion,
    GoalIntakeRequest,
    GoalIntakeResponse,
    GoalQuestion,
)

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None

logger = logging.getLogger(__name__)
INVALID_GOAL_INPUT_DETAIL = "목표로 해석하기 어려운 입력입니다. 달성하고 싶은 일과 기준을 조금 더 구체적으로 입력해 주세요."


class InvalidGoalInputError(ValueError):
    def __init__(self, detail: str = INVALID_GOAL_INPUT_DETAIL):
        super().__init__(detail)
        self.detail = detail


@dataclass
class PlanDraftItem:
    title: str
    description: str
    item_type: str
    estimated_minutes: int
    priority: int
    target_date: date | None
    is_schedulable: bool = True
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanDraft:
    summary: str
    strategy_json: dict[str, Any]
    recommendations_json: dict[str, Any]
    raw_plan_json: dict[str, Any]
    items: list[PlanDraftItem]
    llm_mode: str = "template-fallback"


class StructuredOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMGoalQuestion(StructuredOutputModel):
    key: str
    prompt: str
    answer_type: Literal["text", "number", "date", "boolean", "select"]
    required: bool = True
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)


class GoalIntakeOutput(StructuredOutputModel):
    is_goal_like: bool = True
    clarification_message: str | None = None
    title: str = ""
    description: str | None = None
    inferred_category: GoalCategory = GoalCategory.general
    reasoning: str = ""
    details_json: dict[str, Any] = Field(default_factory=dict)
    suggested_answers_json: dict[str, Any] = Field(default_factory=dict)


class PlanStrategyOutput(StructuredOutputModel):
    category: GoalCategory
    weekly_hours: int = Field(ge=1, le=168)
    focus_areas: list[str]
    routines: list[str]
    target_date: date | None = None
    constraints: str | None = None


class PlanRecommendationsOutput(StructuredOutputModel):
    materials: list[str]
    coach_notes: list[str]
    next_step: str | None = None


class LLMPlanItemOutput(StructuredOutputModel):
    title: str
    description: str
    item_type: str
    estimated_minutes: int = Field(ge=10, le=480)
    priority: int = Field(ge=1, le=3)
    target_date: date | None = None
    is_schedulable: bool = True


class GoalPlanOutput(StructuredOutputModel):
    summary: str
    strategy: PlanStrategyOutput
    recommendations: PlanRecommendationsOutput
    items: list[LLMPlanItemOutput]


class PlanningService:
    MAX_PLAN_ITEM_SESSION_MINUTES = 120
    MAX_GENERATED_PLAN_ITEMS = 240
    MAX_WEEKLY_AVAILABLE_HOURS = 60
    MAX_DAILY_AVAILABLE_MINUTES = 12 * 60
    MAX_ACTIVE_DAYS_PER_WEEK = 7
    MAX_PLANNING_HORIZON_WEEKS = 8
    TARGET_MINUTES_STEP = 30
    SPLIT_MINUTES_STEP = 5
    STUDY_SUBTYPE_TOEIC = "study.toeic"
    STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER = "study.cert.information_processing_engineer"
    KEYBOARD_MASH_SEQUENCES = ("asdf", "qwer", "zxcv", "qwerty", "wasd", "hjkl")

    CATEGORY_HINTS: dict[GoalCategory, tuple[str, ...]] = {
        GoalCategory.study: ("toeic", "toefl", "ielts", "exam", "study", "certificate", "score", "test", "공부", "시험", "자격증", "토익", "토플", "정보처리기사", "정처기"),
        GoalCategory.health: ("diet", "fitness", "health", "workout", "running", "weight", "건강", "운동", "다이어트", "체중"),
        GoalCategory.work: ("portfolio", "project", "career", "job", "resume", "interview", "취업", "포트폴리오", "프로젝트", "이력서"),
        GoalCategory.habit: ("habit", "routine", "sleep", "reading", "journal", "습관", "루틴", "수면", "독서", "기록"),
    }
    CATEGORY_HINTS_KO: dict[GoalCategory, tuple[str, ...]] = {
        GoalCategory.study: ("공부", "시험", "자격증", "토익", "토플", "점수", "학습", "정보처리기사", "정처기"),
        GoalCategory.health: ("건강", "운동", "다이어트", "체중", "헬스", "러닝"),
        GoalCategory.work: ("취업", "포트폴리오", "프로젝트", "이력서", "면접", "커리어", "발표", "데모"),
        GoalCategory.habit: ("습관", "루틴", "수면", "독서", "기록", "일기"),
    }
    STUDY_SUBTYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
        STUDY_SUBTYPE_TOEIC: ("toeic", "토익"),
        STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER: ("정보처리기사", "정보 처리 기사", "정처기"),
    }
    COMMON_QUESTIONS: list[GoalQuestion] = [
        GoalQuestion(key="target_date", prompt="이 목표를 언제까지 완료하거나 1차 점검해야 하나요?", answer_type="date", help_text="마감일이 없으면 가장 먼저 점검할 날짜를 넣어주세요."),
        GoalQuestion(key="weekly_available_hours", prompt="일주일에 안정적으로 확보할 수 있는 시간은 몇 시간인가요?", answer_type="number", help_text="희망 시간이 아니라 실제로 지킬 수 있는 평균 시간을 숫자로 입력해주세요."),
        GoalQuestion(
            key="session_preference",
            prompt="한 번에 어느 정도 길이로 진행하는 편이 가장 잘 맞나요?",
            answer_type="select",
            required=False,
            help_text="자동 배정 시 세션 길이를 조절하는 데 참고합니다.",
            options=["짧게 자주 25-45분", "보통 길이 60-90분", "길게 몰아서 2시간 이상"],
        ),
        GoalQuestion(key="constraints", prompt="계획을 짤 때 반드시 피하거나 고려해야 할 조건이 있나요?", answer_type="text", required=False, help_text="예: 평일은 에너지가 낮음, 고정 일정 직후에는 쉬어야 함"),
    ]
    CATEGORY_QUESTIONS: dict[GoalCategory, list[GoalQuestion]] = {
        GoalCategory.study: [
            GoalQuestion(key="current_level", prompt="현재 수준을 보여주는 가장 최근 기준은 무엇인가요?", answer_type="text", help_text="예: 최근 점수, 진단 결과, 풀 수 있는 문제 난이도"),
            GoalQuestion(key="target_outcome", prompt="목표 시점에 어떤 결과를 만들고 싶나요?", answer_type="text", help_text="예: 850점, 합격권 점수, 특정 단원 완주"),
            GoalQuestion(key="strong_weak_topics", prompt="강한 영역과 약한 영역을 각각 알려주세요.", answer_type="text", help_text="예: 개념은 이해하지만 문제풀이 속도가 느림"),
            GoalQuestion(key="assessment_plan", prompt="진단 테스트나 모의고사를 언제 다시 볼 수 있나요?", answer_type="text", required=False),
            GoalQuestion(key="materials", prompt="계획에 우선 반영할 교재, 강의, 자료가 있나요?", answer_type="text", required=False),
        ],
        GoalCategory.health: [
            GoalQuestion(key="current_state", prompt="현재 몸 상태와 운동 경험은 어느 정도인가요?", answer_type="text", help_text="예: 최근 운동 빈도, 통증 여부, 쉬고 있던 기간"),
            GoalQuestion(key="target_metric", prompt="변화를 확인할 핵심 지표는 무엇인가요?", answer_type="text", help_text="예: 체중, 체지방률, 러닝 거리, 주당 운동 횟수"),
            GoalQuestion(key="activity_capacity", prompt="무리 없이 가능한 운동 강도와 횟수는 어느 정도인가요?", answer_type="text", help_text="예: 주 3회 40분 걷기, 헬스 주 2회"),
            GoalQuestion(key="recovery_limits", prompt="부상, 수면, 회복 때문에 조심해야 할 점이 있나요?", answer_type="text", required=False),
            GoalQuestion(key="diet_constraints", prompt="식단이나 생활습관에서 함께 고려할 조건이 있나요?", answer_type="text", required=False),
        ],
        GoalCategory.work: [
            GoalQuestion(key="current_progress", prompt="현재 완료된 부분과 아직 남은 부분은 어디까지인가요?", answer_type="text"),
            GoalQuestion(key="deliverables", prompt="마감 시점에 제출하거나 보여줘야 하는 결과물은 무엇인가요?", answer_type="text", help_text="예: 발표 자료, 데모, 보고서, 포트폴리오 페이지"),
            GoalQuestion(key="success_definition", prompt="완료됐다고 판단할 품질 기준은 무엇인가요?", answer_type="text", help_text="예: 발표 가능, 리뷰 통과, 핵심 기능 시연 가능"),
            GoalQuestion(key="review_cycle", prompt="피드백이나 검토를 받을 수 있는 시점이 있나요?", answer_type="text", required=False),
            GoalQuestion(key="dependencies", prompt="다른 사람, 자료, 승인처럼 일정에 영향을 주는 의존성이 있나요?", answer_type="text", required=False),
        ],
        GoalCategory.habit: [
            GoalQuestion(key="current_pattern", prompt="현재 이 습관은 얼마나 자주, 어떤 상황에서 하고 있나요?", answer_type="text"),
            GoalQuestion(key="desired_frequency", prompt="목표로 하는 빈도와 최소 성공 기준은 무엇인가요?", answer_type="text", help_text="예: 주 5회, 바쁜 날은 10분만 해도 성공"),
            GoalQuestion(key="trigger", prompt="습관을 시작하게 만들 고정 신호는 무엇이 좋을까요?", answer_type="text", help_text="예: 아침 식사 후, 퇴근 직후, 잠들기 전"),
            GoalQuestion(key="obstacles", prompt="지금까지 이 습관을 방해한 가장 큰 요인은 무엇인가요?", answer_type="text"),
            GoalQuestion(key="accountability", prompt="기록, 알림, 체크리스트처럼 유지에 도움이 되는 장치가 있나요?", answer_type="text", required=False),
        ],
        GoalCategory.general: [
            GoalQuestion(key="current_state", prompt="현재 상황과 이미 진행된 부분을 간단히 설명해주세요.", answer_type="text"),
            GoalQuestion(key="success_definition", prompt="이 목표가 성공했다고 판단할 구체적인 기준은 무엇인가요?", answer_type="text"),
            GoalQuestion(key="priority_scope", prompt="이번 계획에서 가장 먼저 집중해야 할 범위는 어디인가요?", answer_type="text"),
            GoalQuestion(key="first_milestone", prompt="가장 먼저 끝내야 할 중간 목표가 있나요?", answer_type="text", required=False),
            GoalQuestion(key="risks", prompt="계획이 밀릴 가능성이 큰 위험 요소가 있나요?", answer_type="text", required=False),
        ],
    }
    STUDY_SUBTYPE_QUESTIONS: dict[str, list[GoalQuestion]] = {
        STUDY_SUBTYPE_TOEIC: [
            GoalQuestion(key="current_score", prompt="최근 토익 점수나 모의고사 기준 현재 점수는 어느 정도인가요?", answer_type="text", required=False, help_text="모르면 비워두거나 '아직 모름'이라고 적어도 됩니다."),
            GoalQuestion(key="target_score", prompt="목표 토익 점수는 몇 점인가요?", answer_type="number", help_text="예: 750, 850, 900"),
            GoalQuestion(
                key="weak_sections",
                prompt="LC와 RC 중 우선 보완해야 할 영역은 어디인가요?",
                answer_type="select",
                required=False,
                options=["아직 모름", "LC", "RC", "LC와 RC 모두"],
            ),
            GoalQuestion(key="practice_test_access", prompt="실전 모의고사나 기출형 문제를 정기적으로 풀 수 있는 환경인가요?", answer_type="boolean", required=False),
            GoalQuestion(key="vocabulary_routine", prompt="단어 암기는 하루에 어느 정도까지 현실적으로 가능할까요?", answer_type="text", required=False, help_text="예: 하루 20분, 단어장 2일치, 출퇴근 중 앱 복습"),
            GoalQuestion(key="materials", prompt="계획에 우선 반영할 토익 교재, 강의, 앱, 단어장이 있나요?", answer_type="text", required=False),
        ],
        STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER: [
            GoalQuestion(
                key="exam_stage",
                prompt="정보처리기사 필기와 실기 중 어느 범위를 준비하나요?",
                answer_type="select",
                options=["필기", "실기", "필기와 실기 모두", "아직 모름"],
            ),
            GoalQuestion(key="current_progress", prompt="현재 공부 진행 상황과 풀어본 기출 범위는 어디까지인가요?", answer_type="text", help_text="예: 개념 1회독 중, 기출 2개년 풀이 완료, 실기 SQL이 약함"),
            GoalQuestion(key="weak_subjects", prompt="특히 약한 과목이나 문제 유형은 무엇인가요?", answer_type="text", required=False, help_text="예: 데이터베이스, 운영체제, 네트워크, SQL, 약술형"),
            GoalQuestion(key="past_exam_rounds", prompt="목표일까지 기출을 몇 회분 정도 풀 수 있나요?", answer_type="number", required=False),
            GoalQuestion(key="practical_drill_format", prompt="실기 대비가 필요하다면 어떤 방식으로 답안 연습을 할 수 있나요?", answer_type="text", required=False, help_text="예: 손코딩, SQL 직접 실행, 약술형 문장 작성"),
            GoalQuestion(key="materials", prompt="계획에 우선 반영할 교재, 강의, 기출 자료가 있나요?", answer_type="text", required=False),
        ],
    }
    BLUEPRINTS: dict[GoalCategory, dict[str, list[str] | list[tuple[str, str, str, int, int]]]] = {
        GoalCategory.study: {
            "focus_areas": ["assessment", "weak-topic improvement", "practice", "review"],
            "routines": ["weekly diagnostic", "focused study block", "error log review"],
            "materials": ["practice tests", "topic notes", "review notebook"],
            "plan_items": [
                ("diagnostic session", "Identify the biggest gaps first.", "assessment", 90, 3),
                ("focused study block", "Work on the weakest topic with deliberate practice.", "study_block", 60, 3),
                ("mistake review", "Capture recurring mistakes in an error log.", "review", 45, 2),
                ("weekly reflection", "Adjust next week's study emphasis.", "reflection", 30, 2),
            ],
        },
        GoalCategory.health: {
            "focus_areas": ["base fitness", "consistency", "nutrition", "recovery"],
            "routines": ["three weekly workouts", "meal tracking", "weekly check-in"],
            "materials": ["workout log", "metric tracker", "meal guide"],
            "plan_items": [
                ("workout session", "Complete a sustainable workout.", "workout", 60, 3),
                ("nutrition review", "Tighten one realistic nutrition habit.", "nutrition", 30, 2),
                ("recovery block", "Schedule walking, stretching, or light recovery work.", "recovery", 40, 2),
                ("weekly health check", "Review energy, consistency, and your key metric.", "reflection", 20, 2),
            ],
        },
        GoalCategory.work: {
            "focus_areas": ["deliverable clarity", "deep work", "review", "revision"],
            "routines": ["weekly priority setup", "focused execution block", "mid-cycle review"],
            "materials": ["task board", "reference samples", "review checklist"],
            "plan_items": [
                ("deliverable breakdown", "Break the final outcome into work units.", "planning", 45, 3),
                ("deep work session", "Make progress on the highest-value deliverable.", "deep_work", 90, 3),
                ("revision pass", "Incorporate feedback and tighten quality.", "revision", 60, 2),
                ("weekly review", "Review progress and reset priorities.", "reflection", 30, 2),
            ],
        },
        GoalCategory.habit: {
            "focus_areas": ["trigger", "small repetition", "tracking", "reinforcement"],
            "routines": ["start very small", "repeat in one context", "weekly consistency check"],
            "materials": ["habit checklist", "tracking sheet", "reward rule"],
            "plan_items": [
                ("trigger setup", "Choose a reliable cue, time, and place.", "setup", 20, 3),
                ("routine repetition", "Practice the smallest repeatable version.", "routine", 20, 3),
                ("tracking check", "Record whether the habit happened.", "tracking", 10, 2),
                ("habit review", "Adjust the routine to stay easy next week.", "reflection", 15, 2),
            ],
        },
        GoalCategory.general: {
            "focus_areas": ["assessment", "execution", "review"],
            "routines": ["realistic time budgeting", "small repeatable progress", "weekly checkpoint"],
            "materials": ["planning notes", "simple checklist"],
            "plan_items": [
                ("planning block", "Clarify the situation and next useful action.", "planning", 30, 3),
                ("execution block", "Work on the task most tied to goal progress.", "execution", 60, 3),
                ("review checkpoint", "Review what moved forward and decide next.", "reflection", 20, 2),
            ],
        },
    }
    STUDY_SUBTYPE_BLUEPRINTS: dict[str, dict[str, Any]] = {
        STUDY_SUBTYPE_TOEIC: {
            "label": "TOEIC",
            "focus_areas": ["진단과 목표 점수 차이 확인", "매일 어휘 루틴", "LC 파트별 노출", "RC 문법/독해 시간 관리", "모의고사 후 오답 분석"],
            "routines": ["매일 단어 20분", "주 2회 LC shadowing", "주 2회 RC timed practice", "주 1회 오답노트 점검", "2주 1회 실전 모의고사"],
            "materials": ["토익 단어장", "LC/RC 파트별 문제집", "실전 모의고사", "오답노트"],
            "quality_rules": [
                "LC와 RC가 모두 계획에 포함되어야 합니다.",
                "모의고사는 반드시 오답 분석 작업과 짝을 이룹니다.",
                "시험 직전에는 새 개념보다 오답, 시간 관리, 약점 보정 비중을 높입니다.",
                "단어와 짧은 듣기 노출은 장시간 블록보다 반복 루틴으로 설계합니다.",
            ],
            "plan_items": [
                {"title": "토익 진단 세트와 목표 점수 갭 분석", "description": "LC/RC 미니 테스트나 최근 점수를 기준으로 파트별 약점과 목표 점수까지의 차이를 정리합니다.", "item_type": "diagnostic", "estimated_minutes": 100, "priority": 3, "phase": "diagnosis", "offset_ratio": 0.0, "section": "overall"},
                {"title": "단어장 루틴과 오답노트 구조 만들기", "description": "매일 반복할 단어 범위, 복습 주기, 틀린 문제 기록 형식을 먼저 고정합니다.", "item_type": "vocabulary", "estimated_minutes": 40, "priority": 3, "phase": "setup", "offset_ratio": 0.08, "section": "vocabulary"},
                {"title": "LC Part 1-2 짧은 듣기와 shadowing", "description": "짧은 문장/응답 패턴을 듣고 따라 말한 뒤 헷갈린 표현을 오답노트에 남깁니다.", "item_type": "lc_practice", "estimated_minutes": 50, "priority": 3, "phase": "foundation", "offset_ratio": 0.18, "section": "LC"},
                {"title": "RC 문법 핵심 유형 정리", "description": "품사, 동사, 접속사, 전치사처럼 점수 효율이 높은 문법 유형을 문제와 함께 정리합니다.", "item_type": "rc_practice", "estimated_minutes": 60, "priority": 3, "phase": "foundation", "offset_ratio": 0.28, "section": "RC"},
                {"title": "LC Part 3-4 timed set", "description": "대화/담화 문제를 제한 시간 안에 풀고, 놓친 근거 문장과 paraphrasing 표현을 복습합니다.", "item_type": "lc_practice", "estimated_minutes": 70, "priority": 3, "phase": "practice", "offset_ratio": 0.42, "section": "LC"},
                {"title": "RC Part 7 독해 timed practice", "description": "단일/복수 지문을 시간 제한으로 풀고 지문 유형별 시간 사용량을 기록합니다.", "item_type": "rc_practice", "estimated_minutes": 75, "priority": 3, "phase": "practice", "offset_ratio": 0.52, "section": "RC"},
                {"title": "주간 오답노트 압축 리뷰", "description": "반복해서 틀린 어휘, 문법, LC 함정 표현을 묶어 다음 주 우선순위를 정합니다.", "item_type": "mistake_review", "estimated_minutes": 50, "priority": 2, "phase": "review", "offset_ratio": 0.62, "section": "overall"},
                {"title": "실전 모의고사 1회", "description": "가능하면 실제 시험과 같은 순서와 제한 시간으로 풀어 집중력과 시간 배분을 점검합니다.", "item_type": "mock_test", "estimated_minutes": 130, "priority": 3, "phase": "simulation", "offset_ratio": 0.74, "section": "overall"},
                {"title": "모의고사 오답 분석과 파트별 재훈련", "description": "모의고사 직후 틀린 이유를 유형화하고 LC/RC 각각 다음 훈련 블록에 반영합니다.", "item_type": "mistake_review", "estimated_minutes": 90, "priority": 3, "phase": "simulation_review", "offset_ratio": 0.80, "section": "overall"},
                {"title": "시험 직전 약점 보정 스프린트", "description": "새 자료를 늘리기보다 누적 오답, 빈출 단어, 시간 배분 실수를 중심으로 마무리합니다.", "item_type": "final_review", "estimated_minutes": 75, "priority": 3, "phase": "final", "offset_ratio": 0.92, "section": "overall"},
            ],
        },
        STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER: {
            "label": "정보처리기사",
            "focus_areas": ["시험 범위 확정", "과목별 개념 회독", "기출 반복", "오답/빈출 키워드 압축", "실기 답안 표현 훈련"],
            "routines": ["주 1회 기출 세트", "과목별 개념 블록", "오답노트 재풀이", "빈출 키워드 암기", "실기 SQL/약술형 훈련"],
            "materials": ["정보처리기사 기본서", "최근 기출문제", "오답노트", "빈출 키워드 요약표", "SQL/프로그래밍 문제"],
            "quality_rules": [
                "필기/실기 준비 범위를 먼저 확정해야 합니다.",
                "개념 회독만 넣지 말고 기출 풀이와 오답 재풀이가 함께 있어야 합니다.",
                "실기 준비에는 SQL, 프로그래밍, 보안/네트워크, 약술형 답안 표현 훈련이 포함되어야 합니다.",
                "시험 직전에는 빈출 키워드와 오답을 압축 복습합니다.",
            ],
            "plan_items": [
                {"title": "시험 범위 확정과 최근 기출 진단", "description": "필기/실기 범위를 확정하고 최근 기출 1회분으로 과목별 취약도를 확인합니다.", "item_type": "diagnostic", "estimated_minutes": 100, "priority": 3, "phase": "diagnosis", "offset_ratio": 0.0, "section": "overall"},
                {"title": "과목별 개념 1회독 계획 세우기", "description": "소프트웨어 설계, 개발, 데이터베이스, 프로그래밍 언어, 정보시스템 구축관리의 회독 순서를 정합니다.", "item_type": "concept_review", "estimated_minutes": 70, "priority": 3, "phase": "foundation", "offset_ratio": 0.12, "section": "written"},
                {"title": "데이터베이스와 SQL 집중 블록", "description": "정규화, 트랜잭션, SQL 기본/응용 문제를 묶어서 실기까지 이어지는 기반을 만듭니다.", "item_type": "practical_drill", "estimated_minutes": 80, "priority": 3, "phase": "foundation", "offset_ratio": 0.24, "section": "database_sql"},
                {"title": "최근 기출 1회독", "description": "최근 기출을 회차 단위로 풀고 과목별 정답률과 반복 오답을 기록합니다.", "item_type": "past_exam", "estimated_minutes": 120, "priority": 3, "phase": "practice", "offset_ratio": 0.38, "section": "overall"},
                {"title": "기출 오답 재풀이와 빈출 키워드 정리", "description": "틀린 문제를 다시 풀고 암기해야 할 용어, 약어, 보안/네트워크 키워드를 압축합니다.", "item_type": "mistake_review", "estimated_minutes": 80, "priority": 3, "phase": "review", "offset_ratio": 0.50, "section": "overall"},
                {"title": "실기 약술형 답안 표현 훈련", "description": "정의형/서술형 문제를 키워드 중심으로 직접 써보고 채점 기준에 맞게 문장을 다듬습니다.", "item_type": "practical_drill", "estimated_minutes": 70, "priority": 2, "phase": "practical", "offset_ratio": 0.62, "section": "practical"},
                {"title": "프로그래밍/알고리즘 문제 풀이", "description": "출력 예측, 코드 빈칸, 기본 알고리즘 유형을 시간 제한으로 풀고 풀이 과정을 기록합니다.", "item_type": "practical_drill", "estimated_minutes": 75, "priority": 2, "phase": "practical", "offset_ratio": 0.70, "section": "programming"},
                {"title": "실전 모의고사 또는 기출 1회분", "description": "시험 시간에 맞춰 한 회분을 풀고 실제 점수화 기준으로 부족한 파트를 확인합니다.", "item_type": "mock_test", "estimated_minutes": 120, "priority": 3, "phase": "simulation", "offset_ratio": 0.82, "section": "overall"},
                {"title": "최종 오답/빈출 키워드 압축 복습", "description": "새 범위를 늘리지 않고 누적 오답, 빈출 약어, SQL 문법, 약술형 표현을 마지막으로 점검합니다.", "item_type": "final_review", "estimated_minutes": 80, "priority": 3, "phase": "final", "offset_ratio": 0.94, "section": "overall"},
            ],
        },
    }

    def __init__(self, client: Any | None = None):
        self.settings = settings
        self._client = client

    def detect_category(self, title: str, description: str | None = None) -> GoalCategory:
        text = f"{title} {description or ''}".lower()
        for category, keywords in self.CATEGORY_HINTS.items():
            if any(keyword in text for keyword in keywords):
                return category
        for category, keywords in self.CATEGORY_HINTS_KO.items():
            if any(keyword in text for keyword in keywords):
                return category
        return GoalCategory.general

    def detect_study_subtype(self, title: str, description: str | None = None) -> str | None:
        text = self._normalize_for_keyword_match(f"{title} {description or ''}")
        for subtype, keywords in self.STUDY_SUBTYPE_KEYWORDS.items():
            if any(self._normalize_for_keyword_match(keyword) in text for keyword in keywords):
                return subtype
        return None

    def _normalize_for_keyword_match(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()

    def parse_goal_input(self, payload: GoalIntakeRequest) -> GoalIntakeResponse:
        self._ensure_goal_input_is_meaningful(payload.text)
        category, study_subtype = self._classify_goal_input(payload)
        if category == GoalCategory.study and study_subtype in self.STUDY_SUBTYPE_BLUEPRINTS:
            return self._parse_goal_input_with_template(payload)
        if self._can_use_gemini():
            try:
                return self._parse_goal_input_with_gemini(payload)
            except InvalidGoalInputError:
                raise
            except Exception as exc:  # pragma: no cover
                logger.warning("Gemini goal parsing failed; falling back to templates: %s", exc)
        return self._parse_goal_input_with_template(payload)

    def build_plan(self, goal: Goal, answers: dict[str, Any]) -> PlanDraft:
        study_subtype = self._study_subtype_for_goal(goal, answers)
        if (goal.category or GoalCategory.general) == GoalCategory.study and study_subtype in self.STUDY_SUBTYPE_BLUEPRINTS:
            return self._build_plan_with_template(goal, answers)
        if self._can_use_gemini():
            try:
                return self._build_plan_with_gemini(goal, answers)
            except Exception as exc:  # pragma: no cover
                logger.warning("Gemini plan generation failed; falling back to templates: %s", exc)
        return self._build_plan_with_template(goal, answers)

    def _can_use_gemini(self) -> bool:
        if self.settings.llm_model == "template-fallback":
            return False
        return bool(self.settings.gemini_api_key and genai is not None)

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._can_use_gemini():
            return None
        self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def _parse_goal_input_with_gemini(self, payload: GoalIntakeRequest) -> GoalIntakeResponse:
        category_hint, study_subtype = self._classify_goal_input(payload)
        response = self._get_client().models.generate_content(
            model=self.settings.llm_model,
            contents=self._intake_user_prompt(payload, category_hint),
            config=self._build_generation_config(schema=GoalIntakeOutput, system_instruction=self._intake_instructions(), use_tools=False),
        )
        parsed = self._parse_response_model(response, GoalIntakeOutput)
        if not parsed.is_goal_like:
            raise InvalidGoalInputError(self._safe_invalid_goal_detail(parsed.clarification_message))
        category = category_hint if payload.category or study_subtype else parsed.inferred_category
        if category != GoalCategory.study:
            study_subtype = None
        questions = self._questions_for_goal(category, study_subtype)
        details_json = dict(parsed.details_json)
        details_json.update(self._study_subtype_details(study_subtype))
        goal = GoalDraftSuggestion(
            title=(parsed.title or self._suggest_title_from_text(payload.text)).strip(),
            description=self._normalize_description(parsed.description or payload.text),
            category=category,
            details_json=details_json,
            answers_json=parsed.suggested_answers_json,
        )
        return GoalIntakeResponse(goal=goal, reasoning=parsed.reasoning, questions=questions)

    def _build_plan_with_gemini(self, goal: Goal, answers: dict[str, Any]) -> PlanDraft:
        use_tools = self.settings.llm_enable_web_search and self._supports_structured_tools()
        study_subtype = self._study_subtype_for_goal(goal, answers)
        weekly_hours = self._resolve_weekly_hours(answers)
        target_date = goal.target_date or self._resolve_target_date(answers)
        response = self._get_client().models.generate_content(
            model=self.settings.llm_model,
            contents=self._plan_user_prompt(goal, answers),
            config=self._build_generation_config(schema=GoalPlanOutput, system_instruction=self._plan_instructions(), use_tools=use_tools),
        )
        parsed = self._parse_response_model(response, GoalPlanOutput)
        items = [
            PlanDraftItem(
                title=item.title.strip(),
                description=item.description.strip(),
                item_type=item.item_type.strip() or "task",
                estimated_minutes=item.estimated_minutes,
                priority=item.priority,
                target_date=item.target_date,
                is_schedulable=item.is_schedulable,
                metadata_json={"goal_category": goal.category.value, "source": "gemini"},
            )
            for item in parsed.items
        ]
        target_total_minutes = self._target_total_minutes_for_items(weekly_hours, target_date, items)
        items = self._scale_items_to_planning_horizon(
            items,
            weekly_hours,
            target_date,
            target_total_minutes=target_total_minutes,
        )
        items = self._split_plan_items_for_scheduling(items)
        validation = self._validate_study_plan(study_subtype, items, answers) if study_subtype else None
        if validation and not validation["passed"]:
            return self._build_plan_with_template(goal, answers)
        raw_plan_json = parsed.model_dump(mode="json")
        raw_plan_json["items"] = self._plan_items_payload(items)
        raw_plan_json["planning_horizon_days"] = self._planning_horizon_days(target_date)
        raw_plan_json["planning_horizon_weeks"] = self._planning_horizon_weeks(target_date)
        raw_plan_json["target_total_minutes"] = target_total_minutes
        raw_plan_json["research_sources"] = self._extract_research_sources(response)
        if validation:
            raw_plan_json["quality_validation"] = validation
        llm_mode = "gemini-google-search" if use_tools else "gemini"
        strategy_json = parsed.strategy.model_dump(mode="json")
        strategy_json.update(
            {
                "weekly_hours": weekly_hours,
                "target_date": target_date.isoformat() if target_date else None,
                "planning_horizon_days": self._planning_horizon_days(target_date),
                "planning_horizon_weeks": self._planning_horizon_weeks(target_date),
                "target_total_minutes": target_total_minutes,
            }
        )
        return PlanDraft(summary=parsed.summary, strategy_json=strategy_json, recommendations_json=parsed.recommendations.model_dump(mode="json"), raw_plan_json=raw_plan_json, items=items, llm_mode=llm_mode)

    def _parse_goal_input_with_template(self, payload: GoalIntakeRequest) -> GoalIntakeResponse:
        category, study_subtype = self._classify_goal_input(payload)
        answers_json = self._extract_suggested_answers_from_text(payload.text)
        details_json: dict[str, Any] = self._study_subtype_details(study_subtype)
        if answers_json.get("constraints"):
            details_json["inferred_constraints"] = answers_json["constraints"]
        if study_subtype:
            reasoning = f"Keyword routing classified the goal as '{study_subtype}' and prefilled details that were explicit in the text."
        else:
            reasoning = f"Converted the freeform goal into a '{category.value}' draft and prefilled details that were explicit in the text."
        questions = self._questions_for_goal(category, study_subtype)
        goal = GoalDraftSuggestion(
            title=self._suggest_title_from_text(payload.text),
            description=self._normalize_description(payload.text),
            category=category,
            details_json=details_json,
            answers_json=answers_json,
        )
        return GoalIntakeResponse(goal=goal, reasoning=reasoning, questions=questions)

    def _build_plan_with_template(self, goal: Goal, answers: dict[str, Any]) -> PlanDraft:
        category = goal.category or GoalCategory.general
        study_subtype = self._study_subtype_for_goal(goal, answers)
        if category == GoalCategory.study and study_subtype in self.STUDY_SUBTYPE_BLUEPRINTS:
            return self._build_study_subtype_plan_with_template(goal, answers, study_subtype)

        blueprint = self.BLUEPRINTS[category]
        weekly_hours = self._resolve_weekly_hours(answers)
        target_date = goal.target_date or self._resolve_target_date(answers)
        items = self._build_template_items(goal, blueprint["plan_items"], target_date)
        target_total_minutes = self._target_total_minutes_for_items(weekly_hours, target_date, items)
        items = self._scale_items_to_planning_horizon(
            items,
            weekly_hours,
            target_date,
            target_total_minutes=target_total_minutes,
        )
        items = self._split_plan_items_for_scheduling(items)
        summary = f"This is a practical plan for '{goal.title}' based on about {weekly_hours} hours per week."
        strategy_json = {
            "category": category.value,
            "weekly_hours": weekly_hours,
            "target_date": target_date.isoformat() if target_date else None,
            "planning_horizon_days": self._planning_horizon_days(target_date),
            "planning_horizon_weeks": self._planning_horizon_weeks(target_date),
            "target_total_minutes": target_total_minutes,
            "focus_areas": blueprint["focus_areas"],
            "routines": blueprint["routines"],
            "constraints": answers.get("constraints"),
            "preferred_work_times": answers.get("preferred_work_times"),
            "unavailable_times": answers.get("unavailable_times"),
            "session_preference": answers.get("session_preference"),
        }
        recommendations_json = {
            "materials": blueprint["materials"],
            "coach_notes": self._coach_notes(category, answers),
            "next_step": items[0].title if items else None,
        }
        raw_plan_json = {
            "summary": summary,
            "strategy": strategy_json,
            "recommendations": recommendations_json,
            "planning_horizon_days": self._planning_horizon_days(target_date),
            "planning_horizon_weeks": self._planning_horizon_weeks(target_date),
            "target_total_minutes": target_total_minutes,
            "items": self._plan_items_payload(items),
        }
        return PlanDraft(summary=summary, strategy_json=strategy_json, recommendations_json=recommendations_json, raw_plan_json=raw_plan_json, items=items, llm_mode="template-fallback")

    def _build_study_subtype_plan_with_template(self, goal: Goal, answers: dict[str, Any], study_subtype: str) -> PlanDraft:
        blueprint = self.STUDY_SUBTYPE_BLUEPRINTS[study_subtype]
        weekly_hours = self._resolve_weekly_hours(answers)
        target_date = goal.target_date or self._resolve_target_date(answers)
        items = self._build_study_subtype_template_items(goal, blueprint["plan_items"], target_date, study_subtype, answers)
        target_total_minutes = self._target_total_minutes_for_items(weekly_hours, target_date, items)
        items = self._scale_items_to_planning_horizon(
            items,
            weekly_hours,
            target_date,
            target_total_minutes=target_total_minutes,
        )
        items = self._split_plan_items_for_scheduling(items)
        validation = self._validate_study_plan(study_subtype, items, answers)
        label = blueprint["label"]
        user_materials = self._user_materials(answers)
        summary = f"{goal.title} 목표는 {label} 전용 템플릿으로 구성했습니다. 주당 약 {weekly_hours}시간을 기준으로 진단, 핵심 훈련, 실전 점검, 오답 복습이 끊기지 않게 배치합니다."
        strategy_json = {
            "category": GoalCategory.study.value,
            "study_subtype": study_subtype,
            "template_label": label,
            "weekly_hours": weekly_hours,
            "target_date": target_date.isoformat() if target_date else None,
            "planning_horizon_days": self._planning_horizon_days(target_date),
            "planning_horizon_weeks": self._planning_horizon_weeks(target_date),
            "target_total_minutes": target_total_minutes,
            "focus_areas": blueprint["focus_areas"],
            "routines": blueprint["routines"],
            "quality_rules": blueprint["quality_rules"],
            "constraints": answers.get("constraints"),
            "preferred_work_times": answers.get("preferred_work_times"),
            "unavailable_times": answers.get("unavailable_times"),
            "session_preference": answers.get("session_preference"),
            "user_materials": user_materials,
        }
        recommendations_json = {
            "materials": self._study_materials(blueprint["materials"], user_materials),
            "user_materials": user_materials,
            "coach_notes": self._study_coach_notes(study_subtype, answers),
            "next_step": items[0].title if items else None,
        }
        raw_plan_json = {
            "summary": summary,
            "strategy": strategy_json,
            "recommendations": recommendations_json,
            "quality_validation": validation,
            "planning_horizon_days": self._planning_horizon_days(target_date),
            "planning_horizon_weeks": self._planning_horizon_weeks(target_date),
            "target_total_minutes": target_total_minutes,
            "items": self._plan_items_payload(items),
        }
        llm_mode = f"template-fallback-{study_subtype.replace('.', '-')}"
        return PlanDraft(summary=summary, strategy_json=strategy_json, recommendations_json=recommendations_json, raw_plan_json=raw_plan_json, items=items, llm_mode=llm_mode)

    def _intake_instructions(self) -> str:
        return (
            "You turn a user's freeform goal statement into a structured goal draft for an AI planning assistant. "
            "Return only JSON that matches the schema. "
            "Set is_goal_like to false when the input is random text, keyboard mashing, placeholder/test content, only punctuation, or too vague to describe something the user wants to achieve. "
            "When is_goal_like is false, provide a short clarification_message that asks the user to enter a clearer goal instead of inventing a goal. "
            "Infer a short title, a clearer one-sentence description, and the best category among study, health, work, habit, or general. "
            "Only extract details or suggested answers that are explicitly grounded in the user's text. "
            "Write user-facing text in the same language as the user's goal when possible."
        )

    def _plan_instructions(self) -> str:
        return (
            "You generate realistic execution plans for an AI planning assistant. Return only JSON that matches the schema. "
            "Do not assign exact times. Produce work units that can be scheduled later. "
            "Keep each schedulable work unit at 120 minutes or less; split longer work into multiple items. "
            "Prefer sustainable plans over idealized plans. "
            "If the user prompt includes a domain_template, follow its quality_rules and include the required_item_types unless the user's answers make them irrelevant. "
            "Write user-facing text in the same language as the user's goal when possible."
        )

    def _intake_user_prompt(self, payload: GoalIntakeRequest, category_hint: GoalCategory) -> str:
        return json.dumps(
            {
                "today": date.today().isoformat(),
                "freeform_goal_text": payload.text,
                "provided_category": payload.category.value if payload.category else None,
                "category_hint": category_hint.value,
                "allowed_categories": [category.value for category in GoalCategory],
                "important_rule": "Do not invent deadlines, hours, constraints, or a goal when the input is not goal-like.",
            },
            ensure_ascii=False,
        )

    def _plan_user_prompt(self, goal: Goal, answers: dict[str, Any]) -> str:
        study_subtype = self._study_subtype_for_goal(goal, answers)
        return json.dumps(
            {
                "today": date.today().isoformat(),
                "goal": {
                    "title": goal.title,
                    "description": goal.description,
                    "category": goal.category.value,
                    "target_date": goal.target_date.isoformat() if goal.target_date else None,
                    "details_json": goal.details_json,
                },
                "answers_json": answers,
                "weekly_hours_hint": self._resolve_weekly_hours(answers),
                "planning_horizon_days": self._planning_horizon_days(goal.target_date or self._resolve_target_date(answers)),
                "planning_horizon_weeks": self._planning_horizon_weeks(goal.target_date or self._resolve_target_date(answers)),
                "target_total_minutes": self._target_total_minutes(
                    self._resolve_weekly_hours(answers),
                    goal.target_date or self._resolve_target_date(answers),
                ),
                "domain_template": self._domain_template_payload(study_subtype),
                "important_rule": "Do not invent exact schedule times. Generate only schedulable work units. The sum of schedulable estimated_minutes should cover target_total_minutes, which is prorated by days remaining until the target date.",
            },
            ensure_ascii=False,
        )

    def _ensure_goal_input_is_meaningful(self, text: str) -> None:
        cleaned = self._clean_whitespace(text)
        if not cleaned:
            raise InvalidGoalInputError()
        if self.detect_study_subtype(cleaned) or self.detect_category(cleaned) != GoalCategory.general:
            return
        if re.search(r"[가-힣]{2,}", cleaned):
            return

        tokens = re.findall(r"[A-Za-z0-9]+", cleaned)
        if not tokens:
            raise InvalidGoalInputError()

        meaningful_tokens = [token for token in tokens if self._is_meaningful_goal_token(token)]
        if len(meaningful_tokens) >= 2:
            return
        if len(meaningful_tokens) == 1 and len(meaningful_tokens[0]) >= 4:
            return

        raise InvalidGoalInputError()

    def _is_meaningful_goal_token(self, token: str) -> bool:
        normalized = token.lower()
        if len(normalized) <= 1:
            return False
        if self._is_repeated_token(normalized):
            return False
        if any(sequence in normalized for sequence in self.KEYBOARD_MASH_SEQUENCES):
            return False
        return True

    def _is_repeated_token(self, token: str) -> bool:
        if len(token) >= 4 and len(set(token)) == 1:
            return True
        for size in range(1, (len(token) // 2) + 1):
            if len(token) % size == 0 and token == token[:size] * (len(token) // size):
                return True
        return False

    def _safe_invalid_goal_detail(self, detail: str | None) -> str:
        cleaned = self._clean_whitespace(detail) if detail else ""
        if not cleaned:
            return INVALID_GOAL_INPUT_DETAIL
        return cleaned[:240]

    def _classify_goal_input(self, payload: GoalIntakeRequest) -> tuple[GoalCategory, str | None]:
        study_subtype = self.detect_study_subtype(payload.text)
        category = payload.category or (GoalCategory.study if study_subtype else self.detect_category(payload.text))
        if category != GoalCategory.study:
            study_subtype = None
        return category, study_subtype

    def _study_subtype_details(self, study_subtype: str | None) -> dict[str, Any]:
        if not study_subtype:
            return {}
        return {
            "study_subtype": study_subtype,
            "study_subtype_source": "keyword",
            "study_subtype_confidence": 1.0,
        }

    def _questions_for_goal(self, category: GoalCategory, study_subtype: str | None) -> list[GoalQuestion]:
        if category == GoalCategory.study and study_subtype in self.STUDY_SUBTYPE_QUESTIONS:
            return self._normalize_questions(category, self.STUDY_SUBTYPE_QUESTIONS[study_subtype], include_category_defaults=False)
        return self._normalize_questions(category, self.CATEGORY_QUESTIONS[category])

    def _domain_template_payload(self, study_subtype: str | None) -> dict[str, Any] | None:
        if study_subtype not in self.STUDY_SUBTYPE_BLUEPRINTS:
            return None
        blueprint = self.STUDY_SUBTYPE_BLUEPRINTS[study_subtype]
        return {
            "study_subtype": study_subtype,
            "label": blueprint["label"],
            "focus_areas": blueprint["focus_areas"],
            "routines": blueprint["routines"],
            "quality_rules": blueprint["quality_rules"],
            "required_item_types": sorted(self._required_item_types_for_study_subtype(study_subtype)),
        }

    def _normalize_questions(
        self,
        category: GoalCategory,
        questions: list[GoalQuestion] | list[LLMGoalQuestion],
        *,
        include_category_defaults: bool = True,
    ) -> list[GoalQuestion]:
        normalized = [self._to_goal_question(question) for question in questions]
        normalized_map = {question.key: question for question in normalized}
        for required in self.COMMON_QUESTIONS:
            normalized_map.setdefault(required.key, required)
        if include_category_defaults:
            for suggested in self.CATEGORY_QUESTIONS[category]:
                normalized_map.setdefault(suggested.key, suggested)
        ordered_keys = [question.key for question in self.COMMON_QUESTIONS]
        ordered_keys.extend(question.key for question in normalized)
        if include_category_defaults:
            ordered_keys.extend(question.key for question in self.CATEGORY_QUESTIONS[category])
        ordered_keys.extend(key for key in normalized_map if key not in ordered_keys)
        return [normalized_map[key] for key in dict.fromkeys(ordered_keys)]

    def _to_goal_question(self, question: GoalQuestion | LLMGoalQuestion) -> GoalQuestion:
        if isinstance(question, GoalQuestion):
            return question
        return GoalQuestion(key=question.key, prompt=question.prompt, answer_type=question.answer_type, required=question.required, help_text=question.help_text, options=question.options)

    def _split_plan_items_for_scheduling(self, items: list[PlanDraftItem]) -> list[PlanDraftItem]:
        split_items: list[PlanDraftItem] = []
        for item in items:
            split_items.extend(self._split_plan_item_for_scheduling(item))
        return split_items

    def _scale_items_to_planning_horizon(
        self,
        items: list[PlanDraftItem],
        weekly_hours: int,
        target_date: date | None,
        *,
        target_total_minutes: int | None = None,
    ) -> list[PlanDraftItem]:
        schedulable_items = [
            item for item in items if item.is_schedulable and item.estimated_minutes > 0
        ]
        if not schedulable_items:
            return items
        repeatable_items = self._repeatable_plan_items(schedulable_items)

        if target_total_minutes is None:
            target_total_minutes = self._target_total_minutes_for_items(weekly_hours, target_date, items)
        current_total_minutes = sum(item.estimated_minutes for item in schedulable_items)
        expanded = list(items)
        repeat_counts = {
            self._repeat_key(item): 1 for item in repeatable_items
        }
        source_index = 0

        while (
            current_total_minutes < target_total_minutes
            and len(expanded) < self.MAX_GENERATED_PLAN_ITEMS
        ):
            source = repeatable_items[source_index % len(repeatable_items)]
            repeat_key = self._repeat_key(source)
            repeat_counts[repeat_key] = repeat_counts.get(repeat_key, 1) + 1
            repeated = self._repeat_plan_item(
                source,
                repeat_counts[repeat_key],
                weekly_hours=weekly_hours,
                target_total_minutes=target_total_minutes,
            )
            expanded.append(repeated)
            current_total_minutes += repeated.estimated_minutes
            source_index += 1

        return self._redistribute_item_target_dates(expanded, target_date)

    def _repeatable_plan_items(self, items: list[PlanDraftItem]) -> list[PlanDraftItem]:
        one_time_types = {"diagnostic", "setup", "planning", "final_review"}
        one_time_phases = {"diagnosis", "setup", "final"}
        repeatable = [
            item
            for item in items
            if item.item_type not in one_time_types
            and item.metadata_json.get("phase") not in one_time_phases
        ]
        return repeatable or items

    def _repeat_plan_item(
        self,
        item: PlanDraftItem,
        repeat_number: int,
        *,
        weekly_hours: int,
        target_total_minutes: int,
    ) -> PlanDraftItem:
        metadata = dict(item.metadata_json)
        metadata.update(
            {
                "repeat_number": repeat_number,
                "scaled_from_weekly_hours": weekly_hours,
                "target_total_minutes": target_total_minutes,
            }
        )
        return PlanDraftItem(
            title=self._repeat_item_title(item.title, repeat_number),
            description=self._repeat_item_description(item.description, repeat_number),
            item_type=item.item_type,
            estimated_minutes=item.estimated_minutes,
            priority=item.priority,
            target_date=item.target_date,
            is_schedulable=item.is_schedulable,
            metadata_json=metadata,
        )

    def _repeat_key(self, item: PlanDraftItem) -> tuple[str, str]:
        return (item.title, item.item_type)

    def _repeat_item_title(self, title: str, repeat_number: int) -> str:
        suffix = f" ({repeat_number}회차)"
        return f"{title[:200 - len(suffix)].rstrip()}{suffix}"

    def _repeat_item_description(self, description: str, repeat_number: int) -> str:
        note = f"반복 학습/실행 일정 {repeat_number}회차입니다."
        return f"{description}\n\n{note}" if description else note

    def _redistribute_item_target_dates(
        self,
        items: list[PlanDraftItem],
        target_date: date | None,
    ) -> list[PlanDraftItem]:
        schedulable_items = [item for item in items if item.is_schedulable]
        if not schedulable_items:
            return items

        start_date = date.today()
        horizon_end = self._planning_horizon_end(target_date)
        span_days = max((horizon_end - start_date).days, 0)
        denominator = max(len(schedulable_items) - 1, 1)
        for index, item in enumerate(schedulable_items):
            item.target_date = start_date + timedelta(days=round(span_days * index / denominator))
        return items

    def _split_plan_item_for_scheduling(self, item: PlanDraftItem) -> list[PlanDraftItem]:
        max_minutes = self.MAX_PLAN_ITEM_SESSION_MINUTES
        item.estimated_minutes = self._round_minutes_to_step(item.estimated_minutes)
        if not item.is_schedulable or item.estimated_minutes <= max_minutes:
            return [item]

        chunk_minutes = self._split_minutes(item.estimated_minutes, max_minutes)
        chunk_count = len(chunk_minutes)
        chunks: list[PlanDraftItem] = []

        for index, minutes in enumerate(chunk_minutes):
            metadata = dict(item.metadata_json)
            metadata.update(
                {
                    "split_from_estimated_minutes": item.estimated_minutes,
                    "split_part": index + 1,
                    "split_count": chunk_count,
                }
            )
            chunks.append(
                PlanDraftItem(
                    title=self._split_item_title(item.title, index + 1, chunk_count),
                    description=self._split_item_description(item.description, index + 1, chunk_count),
                    item_type=item.item_type,
                    estimated_minutes=minutes,
                    priority=item.priority,
                    target_date=item.target_date,
                    is_schedulable=item.is_schedulable,
                    metadata_json=metadata,
                )
            )
        return chunks

    def _round_minutes_to_step(self, minutes: int) -> int:
        step = self.SPLIT_MINUTES_STEP
        return max(step, ((int(minutes) + step - 1) // step) * step)

    def _split_minutes(self, total_minutes: int, max_minutes: int) -> list[int]:
        step = self.SPLIT_MINUTES_STEP
        total_units = self._round_minutes_to_step(total_minutes) // step
        max_units = max(int(max_minutes) // step, 1)
        chunk_count = (total_units + max_units - 1) // max_units
        base_units, extra_units = divmod(total_units, chunk_count)
        return [
            (base_units + (1 if index < extra_units else 0)) * step
            for index in range(chunk_count)
        ]

    def _split_item_title(self, title: str, part: int, count: int) -> str:
        suffix = f" ({part}/{count})"
        base_title = self._base_split_title(title)
        return f"{base_title[:200 - len(suffix)].rstrip()}{suffix}"

    def _split_item_description(self, description: str, part: int, count: int) -> str:
        return self._clean_split_description(description)

    def _base_split_title(self, title: str) -> str:
        return re.sub(r"(?:\s*\(\d+/\d+\))+$", "", title).strip()

    def _clean_split_description(self, description: str) -> str:
        cleaned = description or ""
        return re.sub(r"(?:\n\s*)*분할된 일정 \d+/\d+입니다\.\s*$", "", cleaned).strip()

    def _plan_items_payload(self, items: list[PlanDraftItem]) -> list[dict[str, Any]]:
        return [
            {
                "title": item.title,
                "description": item.description,
                "item_type": item.item_type,
                "estimated_minutes": item.estimated_minutes,
                "priority": item.priority,
                "target_date": item.target_date.isoformat() if item.target_date else None,
                "is_schedulable": item.is_schedulable,
                "metadata_json": item.metadata_json,
            }
            for item in items
        ]

    def _build_generation_config(self, *, schema: type[BaseModel], system_instruction: str, use_tools: bool):
        thinking_config = self._thinking_config()
        tool_config = self._tool_config() if use_tools else []
        if types is None:
            return {}
        return types.GenerateContentConfig(system_instruction=system_instruction, response_mime_type="application/json", response_json_schema=schema.model_json_schema(), thinking_config=thinking_config, tools=tool_config or None)

    def _thinking_config(self):
        if types is None:
            return None
        model_name = self.settings.llm_model
        effort = (self.settings.llm_reasoning_effort or "").lower()
        if not effort or effort == "none":
            return types.ThinkingConfig(thinking_budget=0) if model_name.startswith("gemini-2.5") else None
        if model_name.startswith("gemini-2.5"):
            budgets = {"minimal": 1024, "low": 1024, "medium": 8192, "high": 24576}
            budget = budgets.get(effort)
            return None if budget is None else types.ThinkingConfig(thinking_budget=budget)
        if model_name.startswith("gemini-3"):
            levels = {"minimal": "low", "low": "low", "medium": "high", "high": "high"}
            level = levels.get(effort)
            return None if level is None else types.ThinkingConfig(thinking_level=level)
        return None

    def _supports_structured_tools(self) -> bool:
        return self.settings.llm_model.startswith("gemini-3")

    def _tool_config(self):
        if types is None or not self.settings.llm_enable_web_search or not self._supports_structured_tools():
            return []
        return [types.Tool(google_search=types.GoogleSearch())]

    def _parse_response_model(self, response: Any, model_type: type[BaseModel]) -> BaseModel:
        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini response did not contain text.")
        try:
            return model_type.model_validate_json(text)
        except ValidationError:
            return model_type.model_validate_json(self._strip_markdown_fence(text))

    def _extract_research_sources(self, response: Any) -> list[str]:
        urls: list[str] = []
        for candidate in getattr(response, "candidates", None) or []:
            grounding_metadata = getattr(candidate, "grounding_metadata", None)
            if grounding_metadata is None:
                continue
            for chunk in getattr(grounding_metadata, "grounding_chunks", []) or []:
                web = getattr(chunk, "web", None)
                url = getattr(web, "uri", None) if web is not None else None
                if url and url not in urls:
                    urls.append(url)
        return urls

    def _strip_markdown_fence(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _resolve_weekly_hours(self, answers: dict[str, Any]) -> int:
        value = self._positive_number(answers.get("weekly_available_hours") or answers.get("weekly_hours"))
        if value is not None:
            return self._clamp_weekly_hours(value)
        daily_minutes = self._positive_number(answers.get("daily_available_minutes"))
        active_days = self._positive_number(
            answers.get("study_days_per_week") or answers.get("active_days_per_week")
        )
        if daily_minutes is not None and active_days is not None:
            daily_minutes = min(daily_minutes, self.MAX_DAILY_AVAILABLE_MINUTES)
            active_days = min(active_days, self.MAX_ACTIVE_DAYS_PER_WEEK)
            return self._clamp_weekly_hours((daily_minutes * active_days) / 60)
        return 6

    def _clamp_weekly_hours(self, value: float) -> int:
        return min(
            max(int(value), 1),
            self.MAX_WEEKLY_AVAILABLE_HOURS,
        )

    def _resolve_target_date(self, answers: dict[str, Any]) -> date | None:
        value = answers.get("target_date")
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _positive_number(self, value: Any) -> float | None:
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        if isinstance(value, str):
            match = re.search(r"(\d+(?:\.\d+)?)", value)
            if match:
                parsed = float(match.group(1))
                return parsed if parsed > 0 else None
        return None

    def _planning_horizon_end(self, target_date: date | None) -> date:
        start_date = date.today()
        horizon_end = target_date or start_date + timedelta(days=42)
        horizon_cap = start_date + timedelta(days=(self.MAX_PLANNING_HORIZON_WEEKS * 7) - 1)
        horizon_end = min(horizon_end, horizon_cap)
        return horizon_end if horizon_end >= start_date else start_date

    def _planning_horizon_days(self, target_date: date | None) -> int:
        start_date = date.today()
        horizon_end = self._planning_horizon_end(target_date)
        return max((horizon_end - start_date).days + 1, 1)

    def _planning_horizon_weeks(self, target_date: date | None) -> int:
        total_days = self._planning_horizon_days(target_date)
        return max((total_days + 6) // 7, 1)

    def _target_total_minutes(self, weekly_hours: int, target_date: date | None) -> int:
        weekly_minutes = self._clamp_weekly_hours(weekly_hours) * 60
        total_days = self._planning_horizon_days(target_date)
        raw_numerator = weekly_minutes * total_days
        step_denominator = 7 * self.TARGET_MINUTES_STEP
        return max(
            self.TARGET_MINUTES_STEP,
            ((raw_numerator + step_denominator - 1) // step_denominator) * self.TARGET_MINUTES_STEP,
        )

    def _target_total_minutes_for_items(
        self,
        weekly_hours: int,
        target_date: date | None,
        items: list[PlanDraftItem],
    ) -> int:
        requested_total_minutes = self._target_total_minutes(weekly_hours, target_date)
        schedulable_items = [
            item for item in items if item.is_schedulable and item.estimated_minutes > 0
        ]
        if not schedulable_items:
            return requested_total_minutes

        repeatable_items = self._repeatable_plan_items(schedulable_items)
        current_total_minutes = sum(item.estimated_minutes for item in schedulable_items)
        remaining_item_slots = max(self.MAX_GENERATED_PLAN_ITEMS - len(items), 0)
        repeat_minutes = [item.estimated_minutes for item in repeatable_items]
        full_cycles, partial_cycle = divmod(remaining_item_slots, len(repeat_minutes))
        max_generated_minutes = (
            current_total_minutes
            + full_cycles * sum(repeat_minutes)
            + sum(repeat_minutes[:partial_cycle])
        )
        return min(requested_total_minutes, max_generated_minutes)

    def _suggest_title_from_text(self, text: str) -> str:
        cleaned = self._clean_whitespace(text)
        first_sentence = re.split(r"(?<=[.!?])\s+|\n+", cleaned, maxsplit=1)[0]
        title = re.sub(
            r"^(i want to|i need to|i'm trying to|my goal is to|want to|need to|목표는|저는|나는)\s+",
            "",
            first_sentence,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"^.+?\s+전까지\s+", "", title)
        title = re.sub(
            r"\b(before|by|until|within)\b.*$|전까지.*$|까지.*$|평일.*$|주말.*$|주당.*$|일주일에.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(
            r"(하고 싶어요|하고 싶습니다|하고 싶다|하려고 해요|하려고 합니다|를 목표로 해요|을 목표로 해요)$",
            "",
            title,
        )
        title = re.sub(
            r"\s*(?:이\s*)?목표(?:입니다|이에요|예요|다)?[.!?。]*$",
            "",
            title,
        )
        title = title.strip(" .,!?:;-")
        if not title:
            title = cleaned[:80].strip(" .,!?:;-")
        if len(title) > 80:
            title = title[:77].rstrip() + "..."
        return title or "New goal"

    def _normalize_description(self, text: str | None) -> str | None:
        if not text:
            return None
        cleaned = self._clean_whitespace(text)
        return cleaned or None

    def _extract_suggested_answers_from_text(self, text: str) -> dict[str, Any]:
        answers: dict[str, Any] = {}
        study_subtype = self.detect_study_subtype(text)
        iso_date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        korean_date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text)
        weekly_hours_match = re.search(
            r"\b(\d+)\s*(hours?|hrs?)\s*(per week|a week|weekly)\b|(?:주당|일주일에)\s*(\d+)\s*시간",
            text,
            flags=re.IGNORECASE,
        )

        if iso_date_match:
            answers["target_date"] = iso_date_match.group(1)
        elif korean_date_match:
            try:
                year, month, day = korean_date_match.groups()
                answers["target_date"] = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                pass

        if weekly_hours_match:
            raw_value = weekly_hours_match.group(1) or weekly_hours_match.group(4)
            if raw_value:
                answers["weekly_available_hours"] = int(raw_value)

        if study_subtype == self.STUDY_SUBTYPE_TOEIC:
            toeic_scores = [
                int(match)
                for match in re.findall(r"(?<!\d)([1-9]\d{2})(?!\d)", text)
                if 100 <= int(match) <= 990
            ]
            if toeic_scores:
                answers["target_score"] = toeic_scores[-1]
            if len(toeic_scores) >= 2:
                answers["current_score"] = str(toeic_scores[0])

        if study_subtype == self.STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER:
            if "필기" in text and "실기" in text:
                answers["exam_stage"] = "필기와 실기 모두"
            elif "필기" in text:
                answers["exam_stage"] = "필기"
            elif "실기" in text:
                answers["exam_stage"] = "실기"

        constraint_sentences = self._extract_constraint_sentences(text)
        if constraint_sentences:
            answers["constraints"] = " ".join(constraint_sentences)

        return answers

    def _extract_constraint_sentences(self, text: str) -> list[str]:
        sentences = [
            self._clean_whitespace(sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
            if sentence.strip()
        ]
        constraint_keywords = (
            "weekday",
            "weekdays",
            "weekend",
            "weekends",
            "morning",
            "evening",
            "night",
            "after",
            "before",
            "commute",
            "busy",
            "평일",
            "주말",
            "아침",
            "저녁",
            "밤",
            "퇴근",
            "수업",
            "바빠",
        )
        return [
            sentence
            for sentence in sentences
            if any(keyword in sentence.lower() for keyword in constraint_keywords)
        ][:2]

    def _clean_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _coach_notes(self, category: GoalCategory, answers: dict[str, Any]) -> list[str]:
        notes = [
            "Favor repeatable routines over an overloaded schedule.",
            "Use a short weekly review to close the gap between plan and execution.",
        ]
        if answers.get("constraints"):
            notes.append(f"Constraints to respect: {answers['constraints']}")
        if category == GoalCategory.study:
            if answers.get("target_outcome"):
                notes.append(f"Target learning outcome: {answers['target_outcome']}")
            if answers.get("strong_weak_topics"):
                notes.append(f"Topic mix to consider: {answers['strong_weak_topics']}")
            if answers.get("assessment_plan"):
                notes.append(f"Assessment checkpoint: {answers['assessment_plan']}")
        if category == GoalCategory.health:
            if answers.get("activity_capacity"):
                notes.append(f"Current activity capacity: {answers['activity_capacity']}")
            if answers.get("recovery_limits"):
                notes.append(f"Recovery limits: {answers['recovery_limits']}")
            if answers.get("diet_constraints"):
                notes.append(f"Diet or recovery constraints: {answers['diet_constraints']}")
        if category == GoalCategory.work:
            if answers.get("success_definition"):
                notes.append(f"Quality bar: {answers['success_definition']}")
            if answers.get("dependencies"):
                notes.append(f"Dependencies to sequence around: {answers['dependencies']}")
        if category == GoalCategory.habit:
            if answers.get("desired_frequency"):
                notes.append(f"Target habit frequency: {answers['desired_frequency']}")
            if answers.get("obstacles"):
                notes.append(f"Known habit blockers: {answers['obstacles']}")
        if category == GoalCategory.general:
            if answers.get("priority_scope"):
                notes.append(f"Initial priority scope: {answers['priority_scope']}")
            if answers.get("risks"):
                notes.append(f"Risks to plan around: {answers['risks']}")
        return notes

    def _study_subtype_for_goal(self, goal: Goal, answers: dict[str, Any]) -> str | None:
        details = goal.details_json or {}
        subtype = details.get("study_subtype") or answers.get("study_subtype")
        if isinstance(subtype, str) and subtype in self.STUDY_SUBTYPE_BLUEPRINTS:
            return subtype
        return self.detect_study_subtype(goal.title, goal.description)

    def _study_coach_notes(self, study_subtype: str, answers: dict[str, Any]) -> list[str]:
        user_materials = self._user_materials(answers)
        if study_subtype == self.STUDY_SUBTYPE_TOEIC:
            notes = [
                "단어, LC 노출, 오답 복습은 짧게라도 반복되도록 유지하세요.",
                "모의고사 점수보다 틀린 이유를 파트별로 분류하는 것이 다음 주 일정 품질을 좌우합니다.",
            ]
            if user_materials:
                notes.append(f"새 자료를 늘리기보다 입력한 자료를 우선 사용하세요: {user_materials}")
            if answers.get("weak_sections") and answers["weak_sections"] != "아직 모름":
                notes.append(f"약점 영역으로 표시한 {answers['weak_sections']} 훈련 비중을 주간 계획에서 우선 배정하세요.")
            if answers.get("target_score"):
                notes.append(f"목표 점수 {answers['target_score']}점 기준으로 실전 세트 후 시간 배분을 반드시 기록하세요.")
            return notes

        if study_subtype == self.STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER:
            notes = [
                "개념 회독만 길게 끌지 말고 기출 풀이와 오답 재풀이를 같은 주기에 묶으세요.",
                "실기는 알고 있는 키워드를 채점 가능한 문장으로 쓰는 훈련이 필요합니다.",
            ]
            if user_materials:
                notes.append(f"입력한 자료 기준으로 회독과 기출 풀이 범위를 잡으세요: {user_materials}")
            if answers.get("exam_stage"):
                notes.append(f"현재 준비 범위는 '{answers['exam_stage']}'로 보고 계획을 해석하세요.")
            if answers.get("weak_subjects"):
                notes.append(f"약점 과목/유형: {answers['weak_subjects']}")
            return notes

        return ["학습 목표는 진단, 연습, 오답 복습, 주간 조정을 한 세트로 운영하세요."]

    def _user_materials(self, answers: dict[str, Any]) -> str | None:
        value = answers.get("materials")
        if value is None:
            return None
        cleaned = self._clean_whitespace(str(value))
        return cleaned or None

    def _study_materials(self, template_materials: list[str], user_materials: str | None) -> list[str]:
        if not user_materials:
            return template_materials
        return [f"사용자 지정 자료: {user_materials}", *template_materials]

    def _description_with_user_materials(self, description: str, user_materials: str | None) -> str:
        if not user_materials:
            return description
        return f"{description} 사용 자료는 입력한 교재/강의를 우선합니다: {user_materials}."

    def _build_study_subtype_template_items(
        self,
        goal: Goal,
        templates: list[dict[str, Any]],
        target_date: date | None,
        study_subtype: str,
        answers: dict[str, Any],
    ) -> list[PlanDraftItem]:
        start_date = date.today()
        horizon_end = target_date or start_date + timedelta(days=42)
        if horizon_end < start_date:
            horizon_end = start_date
        total_days = max((horizon_end - start_date).days, 1)
        items: list[PlanDraftItem] = []
        user_materials = self._user_materials(answers)

        for template in templates:
            if not self._should_include_study_template_item(study_subtype, template, answers):
                continue
            offset_ratio = float(template.get("offset_ratio", 0))
            scheduled_for = start_date + timedelta(days=round(total_days * offset_ratio))
            if scheduled_for > horizon_end:
                scheduled_for = horizon_end
            metadata = {
                "goal_category": GoalCategory.study.value,
                "study_subtype": study_subtype,
                "source": "template-fallback",
                "phase": template.get("phase"),
                "section": template.get("section"),
                "materials": user_materials,
            }
            items.append(
                PlanDraftItem(
                    title=template["title"],
                    description=self._description_with_user_materials(template["description"], user_materials),
                    item_type=template["item_type"],
                    estimated_minutes=int(template["estimated_minutes"]),
                    priority=int(template["priority"]),
                    target_date=scheduled_for,
                    metadata_json=metadata,
                )
            )
        return items

    def _should_include_study_template_item(self, study_subtype: str, template: dict[str, Any], answers: dict[str, Any]) -> bool:
        if study_subtype != self.STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER:
            return True

        exam_stage = str(answers.get("exam_stage") or "").strip()
        section = template.get("section")
        if exam_stage == "필기" and section in {"practical", "programming"}:
            return False
        if exam_stage == "실기" and section == "written":
            return False
        return True

    def _required_item_types_for_study_subtype(self, study_subtype: str, answers: dict[str, Any] | None = None) -> set[str]:
        if study_subtype == self.STUDY_SUBTYPE_TOEIC:
            return {"diagnostic", "vocabulary", "lc_practice", "rc_practice", "mistake_review", "mock_test", "final_review"}
        if study_subtype == self.STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER:
            required = {"diagnostic", "concept_review", "past_exam", "mistake_review", "mock_test", "final_review", "practical_drill"}
            exam_stage = str((answers or {}).get("exam_stage") or "").strip()
            if exam_stage == "필기":
                required.discard("practical_drill")
            if exam_stage == "실기":
                required.discard("concept_review")
            return required
        return set()

    def _validate_study_plan(self, study_subtype: str, items: list[PlanDraftItem], answers: dict[str, Any]) -> dict[str, Any]:
        item_types = {item.item_type for item in items}
        sections = {item.metadata_json.get("section") for item in items}
        required_item_types = self._required_item_types_for_study_subtype(study_subtype, answers)
        checks: list[dict[str, Any]] = []

        for item_type in sorted(required_item_types):
            checks.append(
                {
                    "key": f"has_{item_type}",
                    "passed": item_type in item_types,
                    "message": f"필수 학습 블록 '{item_type}' 포함 여부",
                }
            )

        if study_subtype == self.STUDY_SUBTYPE_TOEIC:
            checks.extend(
                [
                    {"key": "covers_lc", "passed": "LC" in sections, "message": "LC 훈련 포함 여부"},
                    {"key": "covers_rc", "passed": "RC" in sections, "message": "RC 훈련 포함 여부"},
                    {"key": "mock_followed_by_review", "passed": self._has_review_after_mock(items), "message": "모의고사 이후 오답 분석 배치 여부"},
                ]
            )
        elif study_subtype == self.STUDY_SUBTYPE_INFORMATION_PROCESSING_ENGINEER:
            checks.extend(
                [
                    {"key": "uses_past_exam_loop", "passed": {"past_exam", "mistake_review"}.issubset(item_types), "message": "기출 풀이와 오답 재풀이 루프 포함 여부"},
                    {"key": "has_final_keyword_review", "passed": "final_review" in item_types, "message": "시험 직전 키워드/오답 압축 복습 포함 여부"},
                ]
            )

        return {
            "passed": all(check["passed"] for check in checks),
            "checks": checks,
        }

    def _has_review_after_mock(self, items: list[PlanDraftItem]) -> bool:
        mock_index = next((index for index, item in enumerate(items) if item.item_type == "mock_test"), None)
        if mock_index is None:
            return False
        return any(
            item.item_type == "mistake_review" and index > mock_index
            for index, item in enumerate(items)
        )

    def _build_template_items(self, goal: Goal, templates: list[tuple[str, str, str, int, int]], target_date: date | None) -> list[PlanDraftItem]:
        start_date = date.today()
        items: list[PlanDraftItem] = []
        for index, (title, description, item_type, minutes, priority) in enumerate(templates):
            scheduled_for = start_date + timedelta(days=index * 2)
            if target_date and scheduled_for > target_date:
                scheduled_for = target_date
            items.append(
                PlanDraftItem(
                    title=f"{goal.title} - {title}",
                    description=description,
                    item_type=item_type,
                    estimated_minutes=minutes,
                    priority=priority,
                    target_date=scheduled_for,
                    metadata_json={"goal_category": goal.category.value, "source": "template-fallback"},
                )
            )
        return items
