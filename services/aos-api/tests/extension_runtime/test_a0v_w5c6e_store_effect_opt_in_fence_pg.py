"""Disposable-PG Store effect opt-in; never touches the live Store."""

from datetime import datetime, timezone
import time

import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from aos_api.ecom_consistency_store import EcomConsistencyStore, _apply_transaction_scope, _fence_store_transaction
from aos_api.ecom_core_models import DerivedMetricCommand, deterministic_hash
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_ecom_consistency_store import batch, ident, obj, scope


@pytest.fixture
def store_case(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    engine = create_engine('postgresql+psycopg://',
                           creator=lambda: psycopg.connect(runtime_dsn), poolclass=NullPool)
    try:
        yield admin_dsn, EcomConsistencyStore(engine), lease, org, project
    finally:
        engine.dispose()


def _base_command(org, project, *, key='base-1'):
    item = obj('Product', 'store-fence-product', identity=ident('store-fence-product',
                                                               org=org, workspace=project))
    return batch(item, key=key, batch_scope=scope(org=org, workspace=project))


def _derived_command(org, project):
    return DerivedMetricCommand(
        identity=ident('store-fence-product', org=org, workspace=project),
        object_type='Product', stream='catalog', expected_derived_revision=0,
        input_revision=1, input_hash=deterministic_hash({'source': 'isolated'}),
        calculator_version='isolated-v1', derived_props={'quality_score': 5},
        computed_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        idempotency_key='derived-1', actor='isolated-test',
    )


def test_base_and_derived_new_write_and_replay_require_current_holder(store_case):
    _, store, lease, org, project = store_case
    base = _base_command(org, project)
    with pytest.raises(HostLeaseBlocked):
        store.apply_batch(base, host_lease=lease)
    assert lease.acquire() == 1
    assert store.apply_batch(base, host_lease=lease).replayed is False
    assert store.apply_batch(base, host_lease=lease).replayed is True
    derived = _derived_command(org, project)
    assert store.update_derived_metrics(derived, host_lease=lease).replayed is False
    assert store.update_derived_metrics(derived, host_lease=lease).replayed is True
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked):
        store.apply_batch(base, host_lease=lease)
    with pytest.raises(HostLeaseBlocked):
        store.update_derived_metrics(derived, host_lease=lease)


def test_second_guard_failure_rolls_back_store_receipt_and_object(store_case, monkeypatch):
    admin_dsn, store, lease, org, project = store_case
    assert lease.acquire() == 1
    original = _fence_store_transaction
    calls = 0

    def reject_second(conn, current_lease, *, org_id, workspace_id):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise HostLeaseBlocked('HOST_LEASE_TEST_LOST_BEFORE_COMMIT')
        return original(conn, current_lease, org_id=org_id, workspace_id=workspace_id)

    monkeypatch.setattr('aos_api.ecom_consistency_store._fence_store_transaction', reject_second)
    with pytest.raises(HostLeaseBlocked, match='LOST_BEFORE_COMMIT'):
        store.apply_batch(_base_command(org, project), host_lease=lease)
    assert calls == 2
    with psycopg.connect(admin_dsn) as conn:
        for table in ('ecom_object', 'ecom_ingest_receipt'):
            count = conn.execute(f'SELECT count(*) FROM {table} WHERE org_id=%s AND workspace_id=%s',
                                 (org, project)).fetchone()[0]
            assert count == 0


def test_replay_exits_recheck_current_holder(store_case, monkeypatch):
    _, store, lease, org, project = store_case
    assert lease.acquire() == 1
    base = _base_command(org, project)
    derived = _derived_command(org, project)
    store.apply_batch(base, host_lease=lease)
    store.update_derived_metrics(derived, host_lease=lease)
    original = _fence_store_transaction
    calls = 0

    def reject_replay_exit(conn, current_lease, *, org_id, workspace_id):
        nonlocal calls
        calls += 1
        if calls % 2 == 0:
            raise HostLeaseBlocked('HOST_LEASE_TEST_REPLAY_EXIT_LOST')
        return original(conn, current_lease, org_id=org_id, workspace_id=workspace_id)

    monkeypatch.setattr('aos_api.ecom_consistency_store._fence_store_transaction', reject_replay_exit)
    with pytest.raises(HostLeaseBlocked, match='REPLAY_EXIT_LOST'):
        store.apply_batch(base, host_lease=lease)
    with pytest.raises(HostLeaseBlocked, match='REPLAY_EXIT_LOST'):
        store.update_derived_metrics(derived, host_lease=lease)
    assert calls == 4


def test_wrong_scope_rejected_before_transaction(store_case):
    _, store, lease, org, project = store_case
    assert lease.acquire() == 1
    with pytest.raises(HostLeaseBlocked, match='SCOPE_DIFFERS'):
        store.apply_batch(_base_command(org, 'different-project'), host_lease=lease)


def test_store_fence_blocks_concurrent_renew_and_rechecks_database_clock(store_case):
    _, store, lease, org, project = store_case
    short = OptInHostLease(connect=lease._connect, scope=lease.scope,
                           ttl_seconds=5, renew_interval_seconds=1)
    assert short.acquire() == 1
    with store._engine.begin() as conn:
        _apply_transaction_scope(conn, org_id=org, workspace_id=project)
        _fence_store_transaction(conn, short, org_id=org, workspace_id=project)
        with lease._connect() as holder:
            holder.execute("SET lock_timeout='200ms'")
            holder.execute('SET ROLE aos_extension_directory')
            holder.execute("SELECT set_config('aos.org_id',%s,true),"
                           "set_config('aos.project_id',%s,true)", (org, project))
            with pytest.raises(psycopg.errors.LockNotAvailable):
                holder.execute('SELECT extension_runtime_host_lease_renew_a0v_093'
                               '(%s,%s,%s,%s,%s)', (org, project, short._token,
                                                     short._epoch, 5))
        time.sleep(5.1)
        with pytest.raises(HostLeaseBlocked, match='REJECTED'):
            _fence_store_transaction(conn, short, org_id=org, workspace_id=project)
