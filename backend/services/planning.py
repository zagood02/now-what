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
    title: str
    description: str | None = None
    inferred_category: GoalCategory
    reasoning: str
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
    CATEGORY_HINTS: dict[GoalCategory, tuple[str, ...]] = {
        GoalCategory.study: ("toeic", "toefl", "ielts", "exam", "study", "certificate", "score", "test", "공부", "시험", "자격증", "토익", "토플"),
        GoalCategory.health: ("diet", "fitness", "health", "workout", "running", "weight", "건강", "운동", "다이어트", "체중"),
        GoalCategory.work: ("portfolio", "project", "career", "job", "resume", "interview", "취업", "포트폴리오", "프로젝트", "이력서"),
        GoalCategory.habit: ("habit", "routine", "sleep", "reading", "journal", "습관", "루틴", "수면", "독서", "기록"),
    }
    CATEGORY_HINTS_KO: dict[GoalCategory, tuple[str, ...]] = {
        GoalCategory.study: ("공부", "시험", "자격증", "토익", "토플", "점수", "학습"),
        GoalCategory.health: ("건강", "운동", "다이어트", "체중", "헬스", "러닝"),
        GoalCategory.work: ("취업", "포트폴리오", "프로젝트", "이력서", "면접", "커리어", "발표", "데모"),
        GoalCategory.habit: ("습관", "루틴", "수면", "독서", "기록", "일기"),
    }
    COMMON_QUESTIONS: list[GoalQuestion] = [
        GoalQuestion(key="target_date", prompt="What is your target date?", answer_type="date", help_text="Include a final deadline or milestone."),
        GoalQuestion(key="weekly_available_hours", prompt="How many hours per week can you invest?", answer_type="number", help_text="Use a realistic number you can sustain."),
        GoalQuestion(key="constraints", prompt="Any schedule or energy constraints?", answer_type="text", required=False, help_text="Examples: busy weekdays, commuting, low-energy evenings."),
    ]
    CATEGORY_QUESTIONS: dict[GoalCategory, list[GoalQuestion]] = {
        GoalCategory.study: [
            GoalQuestion(key="current_level", prompt="What is your current level or score?", answer_type="text"),
            GoalQuestion(key="strong_weak_topics", prompt="What topics are strong and weak?", answer_type="text"),
            GoalQuestion(key="materials", prompt="What materials are you already using?", answer_type="text", required=False),
        ],
        GoalCategory.health: [
            GoalQuestion(key="current_state", prompt="What is your current condition?", answer_type="text"),
            GoalQuestion(key="target_metric", prompt="What metric are you aiming for?", answer_type="text"),
            GoalQuestion(key="diet_constraints", prompt="Any diet or recovery constraints?", answer_type="text", required=False),
        ],
        GoalCategory.work: [
            GoalQuestion(key="current_progress", prompt="How far along are you now?", answer_type="text"),
            GoalQuestion(key="deliverables", prompt="What final deliverables do you need?", answer_type="text"),
            GoalQuestion(key="review_cycle", prompt="How often can you get feedback?", answer_type="text", required=False),
        ],
        GoalCategory.habit: [
            GoalQuestion(key="current_pattern", prompt="What does your current routine look like?", answer_type="text"),
            GoalQuestion(key="trigger", prompt="What cue could trigger the habit?", answer_type="text"),
            GoalQuestion(key="obstacles", prompt="What has been getting in the way?", answer_type="text"),
        ],
        GoalCategory.general: [
            GoalQuestion(key="current_state", prompt="Briefly describe your current situation.", answer_type="text"),
            GoalQuestion(key="success_definition", prompt="How will you know this goal is successful?", answer_type="text"),
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

    def parse_goal_input(self, payload: GoalIntakeRequest) -> GoalIntakeResponse:
        if self._can_use_gemini():
            try:
                return self._parse_goal_input_with_gemini(payload)
            except Exception as exc:  # pragma: no cover
                logger.warning("Gemini goal parsing failed; falling back to templates: %s", exc)
        return self._parse_goal_input_with_template(payload)

    def build_plan(self, goal: Goal, answers: dict[str, Any]) -> PlanDraft:
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
        category_hint = payload.category or self.detect_category(payload.text)
        response = self._get_client().models.generate_content(
            model=self.settings.llm_model,
            contents=self._intake_user_prompt(payload, category_hint),
            config=self._build_generation_config(schema=GoalIntakeOutput, system_instruction=self._intake_instructions(), use_tools=False),
        )
        parsed = self._parse_response_model(response, GoalIntakeOutput)
        category = payload.category or parsed.inferred_category
        questions = self._normalize_questions(category, self.CATEGORY_QUESTIONS[category])
        goal = GoalDraftSuggestion(
            title=(parsed.title or self._suggest_title_from_text(payload.text)).strip(),
            description=self._normalize_description(parsed.description or payload.text),
            category=category,
            details_json=parsed.details_json,
            answers_json=parsed.suggested_answers_json,
        )
        return GoalIntakeResponse(goal=goal, reasoning=parsed.reasoning, questions=questions)

    def _build_plan_with_gemini(self, goal: Goal, answers: dict[str, Any]) -> PlanDraft:
        use_tools = self.settings.llm_enable_web_search and self._supports_structured_tools()
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
        raw_plan_json = parsed.model_dump(mode="json")
        raw_plan_json["research_sources"] = self._extract_research_sources(response)
        llm_mode = "gemini-google-search" if use_tools else "gemini"
        return PlanDraft(summary=parsed.summary, strategy_json=parsed.strategy.model_dump(mode="json"), recommendations_json=parsed.recommendations.model_dump(mode="json"), raw_plan_json=raw_plan_json, items=items, llm_mode=llm_mode)

    def _parse_goal_input_with_template(self, payload: GoalIntakeRequest) -> GoalIntakeResponse:
        category = payload.category or self.detect_category(payload.text)
        answers_json = self._extract_suggested_answers_from_text(payload.text)
        details_json: dict[str, Any] = {}
        if answers_json.get("constraints"):
            details_json["inferred_constraints"] = answers_json["constraints"]
        reasoning = f"Converted the freeform goal into a '{category.value}' draft and prefilled details that were explicit in the text."
        questions = self._normalize_questions(category, self.CATEGORY_QUESTIONS[category])
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
        blueprint = self.BLUEPRINTS[category]
        weekly_hours = self._resolve_weekly_hours(answers)
        target_date = goal.target_date or self._resolve_target_date(answers)
        items = self._build_template_items(goal, blueprint["plan_items"], target_date)
        summary = f"This is a practical plan for '{goal.title}' based on about {weekly_hours} hours per week."
        strategy_json = {
            "category": category.value,
            "weekly_hours": weekly_hours,
            "target_date": target_date.isoformat() if target_date else None,
            "focus_areas": blueprint["focus_areas"],
            "routines": blueprint["routines"],
            "constraints": answers.get("constraints"),
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
            "items": [
                {
                    "title": item.title,
                    "description": item.description,
                    "item_type": item.item_type,
                    "estimated_minutes": item.estimated_minutes,
                    "priority": item.priority,
                    "target_date": item.target_date.isoformat() if item.target_date else None,
                    "is_schedulable": item.is_schedulable,
                }
                for item in items
            ],
        }
        return PlanDraft(summary=summary, strategy_json=strategy_json, recommendations_json=recommendations_json, raw_plan_json=raw_plan_json, items=items, llm_mode="template-fallback")

    def _intake_instructions(self) -> str:
        return (
            "You turn a user's freeform goal statement into a structured goal draft for an AI planning assistant. "
            "Return only JSON that matches the schema. "
            "Infer a short title, a clearer one-sentence description, and the best category among study, health, work, habit, or general. "
            "Only extract details or suggested answers that are explicitly grounded in the user's text. "
            "Write user-facing text in the same language as the user's goal when possible."
        )

    def _plan_instructions(self) -> str:
        return (
            "You generate realistic execution plans for an AI planning assistant. Return only JSON that matches the schema. "
            "Do not assign exact times. Produce work units that can be scheduled later. "
            "Prefer sustainable plans over idealized plans. "
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
                "important_rule": "Do not invent deadlines, hours, or constraints that are not actually stated.",
            },
            ensure_ascii=False,
        )

    def _plan_user_prompt(self, goal: Goal, answers: dict[str, Any]) -> str:
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
                "important_rule": "Do not invent exact schedule times. Generate only schedulable work units.",
            },
            ensure_ascii=False,
        )

    def _normalize_questions(self, category: GoalCategory, questions: list[GoalQuestion] | list[LLMGoalQuestion]) -> list[GoalQuestion]:
        normalized = [self._to_goal_question(question) for question in questions]
        normalized_map = {question.key: question for question in normalized}
        for required in self.COMMON_QUESTIONS:
            normalized_map.setdefault(required.key, required)
        for suggested in self.CATEGORY_QUESTIONS[category]:
            normalized_map.setdefault(suggested.key, suggested)
        ordered_keys = [question.key for question in self.COMMON_QUESTIONS]
        ordered_keys.extend(question.key for question in self.CATEGORY_QUESTIONS[category])
        ordered_keys.extend(key for key in normalized_map if key not in ordered_keys)
        return [normalized_map[key] for key in ordered_keys]

    def _to_goal_question(self, question: GoalQuestion | LLMGoalQuestion) -> GoalQuestion:
        if isinstance(question, GoalQuestion):
            return question
        return GoalQuestion(key=question.key, prompt=question.prompt, answer_type=question.answer_type, required=question.required, help_text=question.help_text, options=question.options)

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
        value = answers.get("weekly_available_hours") or answers.get("weekly_hours")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
        daily_minutes = answers.get("daily_available_minutes")
        active_days = answers.get("study_days_per_week") or answers.get("active_days_per_week")
        if isinstance(daily_minutes, (int, float)) and isinstance(active_days, (int, float)):
            return max(int((daily_minutes * active_days) / 60), 1)
        return 6

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
        if category == GoalCategory.study and answers.get("strong_weak_topics"):
            notes.append(f"Topic mix to consider: {answers['strong_weak_topics']}")
        if category == GoalCategory.health and answers.get("diet_constraints"):
            notes.append(f"Diet or recovery constraints: {answers['diet_constraints']}")
        return notes

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
