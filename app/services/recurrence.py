from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.fixed_schedule import FixedSchedule

SUPPORTED_RECURRENCE_RULES = ("daily", "weekly", "biweekly")
RECURRENCE_ALIASES = {
    "daily": "daily",
    "everyday": "daily",
    "every_day": "daily",
    "매일": "daily",
    "weekly": "weekly",
    "everyweek": "weekly",
    "every_week": "weekly",
    "매주": "weekly",
    "biweekly": "biweekly",
    "bi-weekly": "biweekly",
    "every2weeks": "biweekly",
    "every_2_weeks": "biweekly",
    "every_two_weeks": "biweekly",
    "격주": "biweekly",
}
RECURRENCE_INTERVALS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "biweekly": timedelta(days=14),
}


@dataclass(frozen=True)
class ScheduleOccurrence:
    start_at: datetime
    end_at: datetime
    occurrence_index: int


def normalize_recurrence_rule(rule: str | None) -> str | None:
    if rule is None:
        return None
    cleaned = rule.strip().lower()
    if not cleaned:
        return None
    return RECURRENCE_ALIASES.get(cleaned)


def expand_fixed_schedule(
    schedule: FixedSchedule,
    *,
    range_start: datetime,
    range_end: datetime,
) -> list[ScheduleOccurrence]:
    if range_end <= range_start:
        return []

    duration = schedule.end_at - schedule.start_at
    if duration <= timedelta(0):
        return []

    recurrence_rule = normalize_recurrence_rule(schedule.recurrence_rule)
    if recurrence_rule is None:
        if schedule.start_at < range_end and schedule.end_at > range_start:
            return [
                ScheduleOccurrence(
                    start_at=schedule.start_at,
                    end_at=schedule.end_at,
                    occurrence_index=0,
                )
            ]
        return []

    interval = RECURRENCE_INTERVALS[recurrence_rule]
    offset = range_start - schedule.start_at - duration
    first_index = max((offset // interval) + 1, 0)
    current_start = schedule.start_at + (interval * first_index)
    current_end = schedule.end_at + (interval * first_index)

    occurrences: list[ScheduleOccurrence] = []
    occurrence_index = first_index
    while current_start < range_end:
        if current_end > range_start:
            occurrences.append(
                ScheduleOccurrence(
                    start_at=current_start,
                    end_at=current_end,
                    occurrence_index=occurrence_index,
                )
            )
        current_start += interval
        current_end += interval
        occurrence_index += 1

    return occurrences
