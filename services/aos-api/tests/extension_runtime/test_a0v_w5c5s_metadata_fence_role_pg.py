"""Disposable-PG metadata connector role probe; no source or Store rows read."""

from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


def _metadata_connector(runtime_dsn):
    @contextmanager
    def connect():
        with psycopg.connect(runtime_dsn, row_factory=dict_row) as conn:
            yield conn
    return connect


def _ingress(connect):
    ingress = object.__new__(ControlledSnapshotIngress)
    ingress._connect = connect
    ingress._schedule_binding = None
    ingress._host_lease = None
    return ingress


def test_original_metadata_transaction_adopts_runtime_and_fences(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    connect = _metadata_connector(runtime_dsn)
    ingress = _ingress(connect)
    with connect() as untouched:
        assert untouched.execute('SELECT current_user AS role').fetchone()['role'] != 'aos_runtime'
    with ingress._transaction(scope) as conn:
        roles = conn.execute('SELECT session_user AS login,current_user AS role').fetchone()
        assert roles['login'] != 'aos_runtime'
        assert roles['role'] == 'aos_runtime'
        assert conn.execute("SELECT current_setting('aos.org_id',true) AS org").fetchone()['org'] == org
        lease.fence_in_transaction(conn, dict(org_id=org, project_id=project))
    with connect() as fresh:
        assert fresh.execute('SELECT current_user AS role').fetchone()['role'] != 'aos_runtime'


def test_metadata_transaction_rejects_non_holder_epoch_and_scope(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    ingress = _ingress(_metadata_connector(runtime_dsn))
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with ingress._transaction(scope) as conn:
            lease.fence_in_transaction(conn, dict(org_id=org, project_id=project))
    assert lease.acquire() == 1
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with ingress._transaction(scope) as conn:
            lease.fence_in_transaction(conn, dict(org_id=org, project_id=project))
    lease._epoch -= 1
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with ingress._transaction(scope) as conn:
            lease.fence_in_transaction(conn, dict(org_id=org, project_id='other-project'))
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with ingress._transaction(scope) as conn:
            lease.fence_in_transaction(conn, dict(org_id=org, project_id=project))
