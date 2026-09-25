"""Disposable-PG guard injection for Attempt heartbeat and terminal transaction."""

from time import monotonic
from uuid import uuid4

import psycopg
import pytest

from aos_api.extension_runtime.generation_attempts import RuntimeAttemptLease
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.extension_runtime.recoverable_store_attempt import (
    RecoverableStoreAttempt, RecoverableStoreAttemptOwner,
)
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


def _attempt(runtime, scope, host_lease=None):
    return RecoverableStoreAttempt(
        connect=runtime, scope=scope,
        lease=RuntimeAttemptLease(uuid4(), 'running', 1, True),
        owner_token='x' * 48, heartbeat_seconds=.05, lease_seconds=.2,
        max_execution_seconds=1, host_lease=host_lease,
    )


def test_default_and_valid_holder_guard_both_transactions(fence_case, monkeypatch):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    calls = []

    def heartbeat(self, conn, **kwargs):
        calls.append('heartbeat')
        attempt._stop.set()
        return RuntimeAttemptLease(kwargs['attempt_id'], 'running', 2, True)

    def settle(self, conn, **kwargs):
        calls.append('settle')
        return RuntimeAttemptLease(kwargs['attempt_id'], kwargs['state'], 3, False)

    monkeypatch.setattr('aos_api.extension_runtime.recoverable_store_attempt.'
                        'PostgresRuntimeAttemptStore.heartbeat', heartbeat)
    monkeypatch.setattr('aos_api.extension_runtime.recoverable_store_attempt.'
                        'PostgresRuntimeAttemptStore.settle', settle)
    attempt = _attempt(runtime, scope, lease)
    attempt._execution_deadline = monotonic() + 1
    attempt._heartbeat()
    assert attempt._error is None
    attempt.__exit__(None, None, None)
    assert calls == ['heartbeat', 'settle']
    default = _attempt(runtime, scope)
    def default_heartbeat(self, conn, **kwargs):
        calls.append('default-heartbeat')
        default._stop.set()
        return RuntimeAttemptLease(kwargs['attempt_id'], 'running', 2, True)
    monkeypatch.setattr('aos_api.extension_runtime.recoverable_store_attempt.'
                        'PostgresRuntimeAttemptStore.heartbeat', default_heartbeat)
    default._execution_deadline = monotonic() + 1
    default._heartbeat()
    assert default._error is None
    default.__exit__(None, None, None)
    assert calls[-2:] == ['default-heartbeat', 'settle']


def test_missing_stale_expired_scope_reject_before_attempt_store(fence_case, monkeypatch):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    def forbidden(*args, **kwargs):
        raise AssertionError('attempt store must not be reached')
    monkeypatch.setattr('aos_api.extension_runtime.recoverable_store_attempt.'
                        'PostgresRuntimeAttemptStore.settle', forbidden)
    monkeypatch.setattr('aos_api.extension_runtime.recoverable_store_attempt.'
                        'PostgresRuntimeAttemptStore.heartbeat', forbidden)
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        _attempt(runtime, scope, lease).__exit__(None, None, None)
    missing_heartbeat = _attempt(runtime, scope, lease)
    missing_heartbeat._execution_deadline = monotonic() + 1
    missing_heartbeat._heartbeat()
    assert isinstance(missing_heartbeat._error, HostLeaseBlocked)
    assert missing_heartbeat.cancellation().is_set()
    assert lease.acquire() == 1
    with pytest.raises(TypeError, match='scope'):
        _attempt(runtime, TenantScope(org, 'other-project'), lease)
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        _attempt(runtime, scope, lease).__exit__(None, None, None)
    lease._epoch -= 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        _attempt(runtime, scope, lease).__exit__(None, None, None)


def test_owner_rejects_fake_lease_before_claim():
    with pytest.raises(TypeError, match='Host lease'):
        RecoverableStoreAttemptOwner(connect=lambda: None, host_lease=object())
