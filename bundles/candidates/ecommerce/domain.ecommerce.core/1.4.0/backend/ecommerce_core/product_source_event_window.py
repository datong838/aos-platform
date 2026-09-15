"""Frozen temporal bounds for trusted product events, never execution authority.

The caller supplies exact approved policy bounds and an authenticated Owner row.
In particular, the payload hash does not authenticate the created_at DB column.
Expired deadlines remain expired; the consumer must record missed outcomes.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from .product_source_event import ProductSourceEvent, validate_product_source_event


@dataclass(frozen=True, slots=True)
class ProductSourceEventWindow:
    event: ProductSourceEvent
    source_updated_at: datetime
    recorded_at: datetime
    deadline: datetime


def _aware(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_TIME_INVALID')
    try:
        return value.astimezone(UTC)
    except (ValueError, OverflowError):
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_TIME_INVALID') from None


def product_source_event_window(
    row: Mapping[str, Any], *, org_id: str, project_id: str,
    effective_from: datetime, effective_until: datetime,
    max_source_age_seconds: int, recovery_window_seconds: int,
) -> ProductSourceEventWindow:
    event = validate_product_source_event(row, org_id=org_id, project_id=project_id)
    source, recorded, deadline = _event_window_times(
        recorded_at=row.get('created_at'), source_updated_at=row['payload']['record'].get('source_updated_at'),
        effective_from=effective_from, effective_until=effective_until,
        max_source_age_seconds=max_source_age_seconds, recovery_window_seconds=recovery_window_seconds)
    return ProductSourceEventWindow(event, source, recorded, deadline.replace(microsecond=0))


def _event_window_times(*, recorded_at, source_updated_at, effective_from, effective_until,
                        max_source_age_seconds, recovery_window_seconds):
    start, end = _aware(effective_from), _aware(effective_until)
    if start >= end:
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_POLICY_INVALID')
    if any(type(value) is not int or value <= 0
           for value in (max_source_age_seconds, recovery_window_seconds)):
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_DURATION_INVALID')
    recorded = _aware(recorded_at)
    if not start <= recorded < end:
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_OUTSIDE_POLICY')
    source_value = source_updated_at
    if not isinstance(source_value, str):
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_TIME_INVALID')
    try:
        source = _aware(datetime.fromisoformat(source_value))
    except (ValueError, OverflowError):
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_TIME_INVALID') from None
    if source > recorded:
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_SOURCE_IN_FUTURE')
    try:
        deadline = min(source + timedelta(seconds=max_source_age_seconds),
                       recorded + timedelta(seconds=recovery_window_seconds), end)
    except OverflowError:
        raise ValueError('PRODUCT_SOURCE_EVENT_WINDOW_DURATION_INVALID') from None
    return source, recorded, deadline.replace(microsecond=0)
