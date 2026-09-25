"""Disposable-PG SQL timeouts around Store's own transaction; no Store rows."""

import psycopg
import pytest

from aos_api.ecom_consistency_store import _fence_store_transaction
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_a0v_w5c6c_isolated_store_transaction_fence_pg import _store_transaction


def test_short_store_transaction_accepts_holder_under_local_timeouts(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    with _store_transaction(runtime_dsn, scope) as conn:
        conn.exec_driver_sql("SET LOCAL lock_timeout='300ms'")
        conn.exec_driver_sql("SET LOCAL statement_timeout='1000ms'")
        _fence_store_transaction(conn, lease, org_id=org, workspace_id=project)
        assert conn.exec_driver_sql('SELECT 1').scalar_one() == 1
        _fence_store_transaction(conn, lease, org_id=org, workspace_id=project)


def test_directory_renew_lock_blocks_store_guard_and_local_timeout_fails_closed(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    with psycopg.connect(directory_dsn) as holder:
        holder.execute('SET ROLE aos_extension_directory')
        holder.execute("SELECT set_config('aos.org_id',%s,true),"
                       "set_config('aos.project_id',%s,true)", (org, project))
        holder.execute('SELECT extension_runtime_host_lease_renew_a0v_093'
                       '(%s,%s,%s,%s,%s)', (org, project, lease._token, lease._epoch, 30))
        with pytest.raises(HostLeaseBlocked, match='REJECTED'):
            with _store_transaction(runtime_dsn, scope) as conn:
                conn.exec_driver_sql("SET LOCAL lock_timeout='200ms'")
                conn.exec_driver_sql("SET LOCAL statement_timeout='1000ms'")
                _fence_store_transaction(conn, lease, org_id=org, workspace_id=project)


def test_statement_timeout_is_per_sql_not_a_total_transaction_budget(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    with pytest.raises(Exception, match='statement timeout'):
        with _store_transaction(runtime_dsn, scope) as conn:
            conn.exec_driver_sql("SET LOCAL statement_timeout='100ms'")
            _fence_store_transaction(conn, lease, org_id=org, workspace_id=project)
            conn.exec_driver_sql('SELECT pg_sleep(0.2)')
