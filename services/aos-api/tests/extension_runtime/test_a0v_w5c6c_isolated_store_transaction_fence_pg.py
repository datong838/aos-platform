"""Disposable-PG SQLAlchemy Store-transaction lease feasibility; no Store rows."""

from contextlib import contextmanager

import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from aos_api.ecom_consistency_store import _apply_transaction_scope
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


class _SameTransactionAdapter:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, statement, values):
        return self._connection.exec_driver_sql(statement, values).mappings()


@contextmanager
def _store_transaction(runtime_dsn, scope):
    engine = create_engine('postgresql+psycopg://',
                           creator=lambda: psycopg.connect(runtime_dsn), poolclass=NullPool)
    try:
        with engine.begin() as conn:
            # Match Store's read-write transaction: a0v_094 takes FOR SHARE
            # locks, but this fixture never writes a Store row.
            _apply_transaction_scope(conn, org_id=scope.org_id, workspace_id=scope.project_id)
            assert conn.exec_driver_sql('SELECT current_user').scalar_one() == 'aos_runtime'
            yield conn
    finally:
        engine.dispose()


def _fence(lease, conn, scope):
    lease.fence_in_transaction(_SameTransactionAdapter(conn),
                               dict(org_id=scope.org_id, project_id=scope.project_id))


def test_same_store_transaction_accepts_holder_and_rejects_absent(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    with _store_transaction(runtime_dsn, scope) as conn:
        with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
            _fence(lease, conn, scope)
    assert lease.acquire() == 1
    for _ in range(3):
        with _store_transaction(runtime_dsn, scope) as conn:
            _fence(lease, conn, scope)
            assert conn.exec_driver_sql('SELECT 1').scalar_one() == 1


def test_scope_epoch_and_expiry_block_before_store_body(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    assert lease.acquire() == 1
    with _store_transaction(runtime_dsn, scope) as conn:
        with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
            _fence(lease, conn, TenantScope(org, 'other-project'))
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with _store_transaction(runtime_dsn, scope) as conn:
            _fence(lease, conn, scope)
    lease._epoch -= 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with _store_transaction(runtime_dsn, scope) as conn:
            _fence(lease, conn, scope)
