"""Small deterministic five-field Cron matcher for Logic automation policies."""

from __future__ import annotations

from datetime import datetime


def _matches_field(field: str, value: int, minimum: int, maximum: int) -> bool:
    def match_atom(atom: str) -> bool:
        base, slash, step_raw = atom.partition("/")
        step = int(step_raw) if slash else 1
        if step < 1:
            raise ValueError("cron step must be positive")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_raw, end_raw = base.split("-", 1)
            start, end = int(start_raw), int(end_raw)
        else:
            start = end = int(base)
        if start < minimum or end > maximum or start > end:
            raise ValueError("cron field is outside its valid range")
        return start <= value <= end and (value - start) % step == 0

    return any(match_atom(atom.strip()) for atom in field.split(",") if atom.strip())


def cron_matches(expression: str, moment: datetime) -> bool:
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError("cron expression must contain five fields")
    minute, hour, day, month, weekday = fields
    cron_weekday = (moment.weekday() + 1) % 7
    return all(
        (
            _matches_field(minute, moment.minute, 0, 59),
            _matches_field(hour, moment.hour, 0, 23),
            _matches_field(day, moment.day, 1, 31),
            _matches_field(month, moment.month, 1, 12),
            _matches_field(weekday, cron_weekday, 0, 6),
        )
    )


def validate_cron_expression(expression: str) -> str:
    cleaned = expression.strip()
    cron_matches(cleaned, datetime(2026, 1, 1, 0, 0))
    return cleaned
