"""Explicit PreparationConsumer fence uses its outbox transaction in disposable PG."""

from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
from aos_api.extension_runtime.preparation_worker import PreparationWorker
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5i_host_lease_pg import host_lease_case


def _connections(directory_dsn, runtime_dsn):
    @contextmanager
    def directory():
        with psycopg.connect(directory_dsn, row_factory=dict_row) as conn:
            yield conn

    @contextmanager
    def runtime():
        with psycopg.connect(runtime_dsn, autocommit=True, row_factory=dict_row) as conn:
            conn.execute("SET ROLE aos_runtime")
            yield conn

    return directory, runtime


def test_explicit_fence_guards_same_consumer_transaction(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    assert lease.acquire() == 1
    scope = dict(org_id=org, project_id=project)
    with consumer_connection(runtime, scope, fence=lease.fence_in_transaction) as conn:
        assert conn.execute("SELECT current_user AS role").fetchone()["role"] == "aos_runtime"
    worker = object.__new__(PreparationWorker)
    consumer = PreparationConsumer(connect=runtime, worker=worker,
                                   installation_id=uuid4(), host_lease=lease, **scope)
    assert consumer._claim() is None
    lease._epoch += 1  # isolated fault injection: stale/mismatched holder
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        consumer._claim()
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        consumer._finish(object())


def test_default_consumer_connection_does_not_call_new_guard(fence_case):
    _, _, runtime_dsn, org, project, _ = fence_case
    _, runtime = _connections(runtime_dsn, runtime_dsn)
    with consumer_connection(runtime, dict(org_id=org, project_id=project)) as conn:
        assert conn.execute("SELECT 1 AS alive").fetchone()["alive"] == 1


def test_unacquired_opt_in_lease_rejects_before_outbox_claim(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    worker = object.__new__(PreparationWorker)
    consumer = PreparationConsumer(connect=runtime, worker=worker,
                                   installation_id=uuid4(), host_lease=lease,
                                   org_id=org, project_id=project)
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_INPUT_DIFFERS"):
        consumer._claim()
