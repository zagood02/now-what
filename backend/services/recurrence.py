from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.models.fixed_schedule import FixedSchedule

SUPPORTED_RECURRENCE_RULES = ("daily", "weekly", "biweekly", "monthly")
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
    "monthly": "monthly",
    "month": "monthly",
    "everymonth": "monthly",
    "every_month": "monthly",
    "매월": "monthly",
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


def add_months(date: datetime, months: int) -> datetime:
    month = date.month - 1 + months
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


def _get_next_weekday_on_or_after(start_date: datetime, target_weekday: int) -> datetime:
    days_diff = (target_weekday - start_date.weekday() + 7) % 7
    return start_date + timedelta(days=days_diff)


def expand_fixed_schedule(
    schedule: FixedSchedule,
    *,
    range_start: datetime,
    range_end: datetime,
) -> list[ScheduleOccurrence]:
    if range_end <= range_start:
        return []

    # Convert schedule datetimes to naive if they are timezone-aware
    start_at = schedule.start_at
    end_at = schedule.end_at
    if start_at.tzinfo is not None:
        start_at = start_at.replace(tzinfo=None)
    if end_at.tzinfo is not None:
        end_at = end_at.replace(tzinfo=None)

    duration = end_at - start_at
    if duration <= timedelta(0):
        return []

    recurrence_rule = normalize_recurrence_rule(schedule.recurrence_rule)
    if recurrence_rule is None:
        if start_at < range_end and end_at > range_start:
            return [
                ScheduleOccurrence(
                    start_at=start_at,
                    end_at=end_at,
                    occurrence_index=0,
                )
            ]
        return []

    if recurrence_rule == "monthly":
        occurrences: list[ScheduleOccurrence] = []
        current_start = start_at
        current_end = end_at

        while current_end <= range_start:
            current_start = add_months(current_start, 1)
            current_end = add_months(current_end, 1)

        occurrence_index = 0
        while current_start < range_end:
            if current_end > range_start:
                occurrences.append(
                    ScheduleOccurrence(
                        start_at=current_start,
                        end_at=current_end,
                        occurrence_index=occurrence_index,
                    )
                )
            current_start = add_months(current_start, 1)
            current_end = add_months(current_end, 1)
            occurrence_index += 1

        return occurrences

    interval = RECURRENCE_INTERVALS[recurrence_rule]

    if schedule.day_of_week is not None and recurrence_rule in ("weekly", "biweekly"):
        python_weekday = (schedule.day_of_week - 1) % 7
        anchor_date = start_at
        first_event_date = _get_next_weekday_on_or_after(range_start, python_weekday)

        if first_event_date < anchor_date:
            first_event_date = _get_next_weekday_on_or_after(anchor_date, python_weekday)

        if recurrence_rule == "biweekly":
            weeks_since_anchor = (first_event_date.date() - anchor_date.date()).days // 7
            if weeks_since_anchor % 2 != 0:
                first_event_date += timedelta(days=7)

        current_start = start_at.replace(
            year=first_event_date.year,
            month=first_event_date.month,
            day=first_event_date.day,
        )
        current_end = end_at.replace(
            year=first_event_date.year,
            month=first_event_date.month,
            day=first_event_date.day,
        )
        occurrence_index = 0
    else:
        offset = range_start - start_at - duration
        first_index = max((offset // interval) + 1, 0)
        current_start = start_at + (interval * first_index)
        current_end = end_at + (interval * first_index)
        occurrence_index = first_index

    occurrences: list[ScheduleOccurrence] = []
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
