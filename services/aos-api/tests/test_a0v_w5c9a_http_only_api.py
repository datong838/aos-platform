import importlib.util
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def guard(monkeypatch):
    root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    spec = importlib.util.spec_from_file_location(
        'w5c9a_http_lease_guard_test', root/'scripts/a0v_w5c9a_http_only_api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lease(path, task, expiry, **changes):
    item = {'task_id': task, 'owner': 'm1', 'status': 'ACTIVE',
            'scope': ['local-process/aos-api-18181'],
            'lease_expires_at': expiry.isoformat()}
    item.update(changes)
    path.write_text(json.dumps({'leases': [item]}))


def test_exact_valid_lease_deadline(guard, tmp_path):
    path = tmp_path/'leases.json'
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    expiry = now + timedelta(hours=1)
    _lease(path, guard.TASK, expiry)
    assert guard.lease_deadline(path, now) == expiry


@pytest.mark.parametrize('change', [
    {'owner': 'other'}, {'status': 'EXPIRED'},
    {'scope': ['local-process/other']}, {'task_id': 'OTHER'},
])
def test_wrong_lease_fails_closed(guard, tmp_path, change):
    path = tmp_path/'leases.json'
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    _lease(path, guard.TASK, now + timedelta(hours=1), **change)
    assert guard.lease_deadline(path, now) is None


def test_missing_duplicate_malformed_and_expired_fail_closed(guard, tmp_path):
    path = tmp_path/'leases.json'
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    assert guard.lease_deadline(path, now) is None
    path.write_text('{bad')
    assert guard.lease_deadline(path, now) is None
    _lease(path, guard.TASK, now)
    assert guard.lease_deadline(path, now) is None
    item = json.loads(path.read_text())['leases'][0]
    path.write_text(json.dumps({'leases': [item, item]}))
    assert guard.lease_deadline(path, now) is None


def test_expiry_and_early_revocation_trigger_injected_stop(guard, tmp_path):
    path = tmp_path/'leases.json'
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    expiry = now + timedelta(seconds=2)
    _lease(path, guard.TASK, expiry)
    clock = [now]
    stops = []

    class FakeEvent:
        def is_set(self):
            return False

        def wait(self, seconds):
            assert 0 < seconds <= 30
            clock[0] += timedelta(seconds=seconds)
            return False

    guard.watch_lease(path, FakeEvent(), lambda: stops.append('expired'),
                      clock=lambda: clock[0])
    assert stops == ['expired']

    _lease(path, guard.TASK, now + timedelta(hours=1))
    clock[0] = now
    stops.clear()

    class RevokeEvent(FakeEvent):
        def wait(self, seconds):
            _lease(path, guard.TASK, now + timedelta(hours=1), status='EXPIRED')
            return False

    guard.watch_lease(path, RevokeEvent(), lambda: stops.append('revoked'),
                      clock=lambda: clock[0])
    assert stops == ['revoked']


@pytest.mark.parametrize('action,expected_starts', [('serve', 1), ('check', 0)])
def test_only_serve_wires_process_guard(guard, monkeypatch, action, expected_starts):
    starts = []

    class FakeThread:
        def __init__(self, **kwargs):
            assert kwargs['name'] == 'a0v-w5c9a-lease-guard'

        def start(self):
            starts.append('started')

    monkeypatch.setattr(guard.threading, 'Thread', FakeThread)
    monkeypatch.setattr(guard, 'lease_deadline',
                        lambda *_: datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setattr(guard, 'load_launcher',
                        lambda: SimpleNamespace(main=lambda: None))
    monkeypatch.setattr(guard.sys, 'argv', ['wrapper', action, '--output', 'ignored'])
    guard.main()
    assert len(starts) == expected_starts
