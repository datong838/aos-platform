"""Disposable-PG Single ingress metadata fence; no source read or Store effect."""

import psycopg
import pytest

from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_a0v_w5c5s_metadata_fence_role_pg import _metadata_connector, _ingress


def test_default_and_holder_guard_each_ingress_transaction(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    ingress = _ingress(_metadata_connector(runtime_dsn))
    ingress._host_lease = None
    with ingress._transaction(scope) as conn:
        assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_runtime'
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    ingress._host_lease = lease
    for _ in range(3):
        with ingress._transaction(scope) as conn:
            assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_runtime'
    with ingress._run_transaction(scope, run_id='no-schedule-binding') as conn:
        assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_runtime'


def test_missing_stale_expired_and_wrong_scope_block_ingress(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    ingress = _ingress(_metadata_connector(runtime_dsn))
    ingress._host_lease = lease
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with ingress._transaction(scope):
            raise AssertionError('Ingress body must not run')
    assert lease.acquire() == 1
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with ingress._transaction(TenantScope(org, 'other-project')):
            raise AssertionError('Ingress body must not run')
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with ingress._transaction(scope):
            raise AssertionError('Ingress body must not run')
    lease._epoch -= 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with ingress._transaction(scope):
            raise AssertionError('Ingress body must not run')
