"""Disposable-PG managed lease liveness; never proves fleet completeness."""

import psycopg
import pytest

from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_a0v_w5c6c_isolated_store_transaction_fence_pg import _store_transaction, _fence


def _lease(fence_case):
    admin, directory_dsn, runtime_dsn, org, project, _ = fence_case
    connect, _ = _connections(directory_dsn, runtime_dsn)
    return admin, runtime_dsn, org, project, OptInHostLease(
        connect=connect, scope=TenantScope(org, project))


def test_managed_holder_epoch_and_db_clock_support_bounded_liveness(fence_case):
    admin, runtime, org, project, first = _lease(fence_case)
    assert first.acquire() == 1
    first.renew()
    with _store_transaction(runtime, first.scope) as conn:
        _fence(first, conn, first.scope)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                     "SET expires_at=clock_timestamp()-interval '1 second' "
                     "WHERE org_id=%s AND project_id=%s", (org, project))
    second = OptInHostLease(connect=first._connect, scope=first.scope)
    assert second.acquire() == 2
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with _store_transaction(runtime, first.scope) as conn:
            _fence(first, conn, first.scope)
    with _store_transaction(runtime, second.scope) as conn:
        _fence(second, conn, second.scope)


def test_worker_guard_serializes_managed_release_until_transaction_exits(fence_case):
    _, runtime, org, project, lease = _lease(fence_case)
    assert lease.acquire() == 1
    with _store_transaction(runtime, lease.scope) as conn:
        _fence(lease, conn, lease.scope)
        with lease._connect() as holder:
            holder.execute("SET lock_timeout='200ms'")
            holder.execute('SET ROLE aos_extension_directory')
            holder.execute("SELECT set_config('aos.org_id',%s,true),"
                           "set_config('aos.project_id',%s,true)", (org, project))
            with pytest.raises(psycopg.errors.LockNotAvailable):
                holder.execute('SELECT extension_runtime_host_lease_release_a0v_093'
                               '(%s,%s,%s,%s)', (org, project, lease._token, lease._epoch))
    lease.release()


def test_managed_lease_does_not_claim_nonmanaged_or_remote_host_exclusion():
    from a0v_w5c6j_host_topology_discovery import classify
    result = classify({
        'knownLauncherPids': [],
        'managedDirectory': {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY'},
        'databaseSessions': {'knownLoginSessions': 0, 'remoteClientSessions': 0,
                             'unknownClientSessions': 0},
    })
    assert result['topologyComplete'] is False
    assert result['closureAuthorized'] is False
