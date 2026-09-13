from copy import deepcopy
from datetime import UTC, datetime, timedelta
from dataclasses import FrozenInstanceError

import pytest

from test_product_source_event import event, rehash
from ecommerce_core.product_source_event_window import product_source_event_window

AT = datetime(2026, 9, 13, 6, tzinfo=UTC)


@pytest.fixture
def timed_event(event):
    event['created_at'] = AT
    event['payload']['record']['source_updated_at'] = AT.isoformat()
    rehash(event)
    return event


def window(row, **overrides):
    params = dict(org_id='org-a', project_id='workspace-a',
                  effective_from=AT - timedelta(days=1),
                  effective_until=AT + timedelta(days=1),
                  max_source_age_seconds=3600, recovery_window_seconds=600)
    params.update(overrides)
    return product_source_event_window(row, **params)


def test_frozen_replay_and_input_preserved(timed_event):
    before = deepcopy(timed_event)
    result = window(timed_event)
    assert result == window(timed_event)
    assert result.deadline == AT + timedelta(seconds=600)
    assert result.event.source_event_id == timed_event['event_key']
    assert timed_event == before
    with pytest.raises(FrozenInstanceError):
        result.deadline = AT


def test_old_source_does_not_become_fresh_on_ingestion(timed_event):
    timed_event['payload']['record']['source_updated_at'] = (AT - timedelta(hours=2)).isoformat()
    rehash(timed_event)
    assert window(timed_event).deadline == AT - timedelta(hours=1)


def test_deadline_capped_by_policy_and_floored_not_extended(timed_event):
    end = AT + timedelta(seconds=10, microseconds=999999)
    assert window(timed_event, effective_until=end).deadline == AT + timedelta(seconds=10)


def test_equivalent_timezone_and_microsecond_source(timed_event):
    timed_event['payload']['record']['source_updated_at'] = '2026-09-13T13:59:59.999999+08:00'
    rehash(timed_event)
    result = window(timed_event, max_source_age_seconds=1)
    assert result.source_updated_at == AT - timedelta(microseconds=1)
    assert result.deadline == AT


@pytest.mark.parametrize('key,value', [
    ('max_source_age_seconds', True), ('max_source_age_seconds', 0),
    ('max_source_age_seconds', 1.0), ('max_source_age_seconds', 10**30),
    ('recovery_window_seconds', -1), ('recovery_window_seconds', False),
    ('effective_from', AT.replace(tzinfo=None)), ('effective_until', None),
    ('effective_until', AT - timedelta(days=2)),
    ('effective_from', AT + timedelta(microseconds=1)), ('effective_until', AT),
])
def test_invalid_policy_and_outside_interval_rejected(timed_event, key, value):
    with pytest.raises(ValueError, match='^PRODUCT_SOURCE_EVENT_WINDOW_'):
        window(timed_event, **{key: value})


@pytest.mark.parametrize('value', [None, True, 'not-a-date', '2026-09-13T06:00:00',
                                 '2026-09-13T06:00:01+00:00'])
def test_invalid_or_future_source_time_rejected(timed_event, value):
    timed_event['payload']['record']['source_updated_at'] = value
    rehash(timed_event)
    with pytest.raises(ValueError, match='^PRODUCT_SOURCE_EVENT_WINDOW_'):
        window(timed_event)


@pytest.mark.parametrize('value', [None, AT.isoformat(), AT.replace(tzinfo=None)])
def test_owner_recorded_timestamp_must_be_aware_datetime(timed_event, value):
    timed_event['created_at'] = value
    with pytest.raises(ValueError, match='^PRODUCT_SOURCE_EVENT_WINDOW_'):
        window(timed_event)


def test_hash_and_scope_still_required(timed_event):
    with pytest.raises(ValueError, match='SCOPE_MISMATCH'):
        window(timed_event, org_id='other')
    timed_event['payload']['record']['source_updated_at'] = (AT - timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match='HASH_MISMATCH'):
        window(timed_event)
