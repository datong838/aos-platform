"""Disposable-PG Recovery metadata entry; no saved group is resumed."""

import psycopg
import pytest

from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_a0v_w5c5s_metadata_fence_role_pg import _metadata_connector


def _runtime(connect, host_lease=None):
    runtime = object.__new__(PipelineSnapshotGroupRecoveryRuntime)
    runtime._connect = connect
    runtime._host_lease = host_lease
    return runtime


def test_default_and_holder_enter_recovery_root_transaction(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    connect = _metadata_connector(runtime_dsn)
    with _runtime(connect)._transaction(scope) as conn:
        assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_runtime'
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    with _runtime(connect, lease)._transaction(scope) as conn:
        assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_runtime'


def test_missing_stale_expired_and_wrong_scope_block_recovery_root(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    runtime = _runtime(_metadata_connector(runtime_dsn), lease)
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with runtime._transaction(scope):
            raise AssertionError('saved recovery body must not run')
    assert lease.acquire() == 1
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with runtime._transaction(TenantScope(org, 'other-project')):
            raise AssertionError('saved recovery body must not run')
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with runtime._transaction(scope):
            raise AssertionError('saved recovery body must not run')
    lease._epoch -= 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with runtime._transaction(scope):
            raise AssertionError('saved recovery body must not run')
