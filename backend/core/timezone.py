from datetime import datetime, timedelta, timezone


KST = timezone(timedelta(hours=9), "KST")


def normalize_to_kst_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(KST).replace(tzinfo=None)


def normalize_optional_to_kst_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return normalize_to_kst_naive(value)
