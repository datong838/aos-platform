"""Disable consumer and executor use one opt-in holder in separate PG transactions."""

import psycopg
import pytest

from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


def _consumer(runtime, lease=None):
    calls = []
    consumer = RuntimeDisableConsumer(connect=runtime, installation_store=None,
        check_current_permission=lambda **kwargs: calls.append("permission"),
        check_drained=lambda **kwargs: calls.append("drain"), host_lease=lease)
    return consumer, calls


def test_outer_and_executor_transactions_share_exact_holder(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    assert lease.acquire() == 1
    consumer, calls = _consumer(runtime, lease)
    assert consumer.executor.host_lease is consumer.host_lease is lease
    assert consumer.claim_once(org_id=org, project_id=project) is None
    scope = dict(org_id=org, project_id=project)
    with consumer.executor._connection(scope) as conn:
        assert conn.execute("SELECT current_user AS role").fetchone()["role"] == "aos_runtime"
    lease._epoch += 1  # isolated lost-authority injection
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        consumer.claim_once(org_id=org, project_id=project)
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        with consumer.executor._connection(scope):
            pytest.fail("executor entered after lost Host authority")
    assert calls == []


def test_default_absent_expired_and_wrong_scope_fail_closed(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    default, _ = _consumer(runtime)
    assert default.claim_once(org_id=org, project_id=project) is None
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    guarded, calls = _consumer(runtime, lease)
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_INPUT_DIFFERS"):
        guarded.claim_once(org_id=org, project_id=project)
    assert lease.acquire() == 1
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_INPUT_DIFFERS"):
        guarded.claim_once(org_id=org, project_id="other-project")
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        guarded.claim_once(org_id=org, project_id=project)
    assert calls == []
