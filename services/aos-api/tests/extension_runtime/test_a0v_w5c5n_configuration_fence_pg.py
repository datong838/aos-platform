"""ConfigurationConsumer opt-in guard uses disposable PG and original transactions."""

import psycopg
import pytest

from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


def _consumer(runtime, lease=None):
    calls = []
    consumer = ConfigurationConsumer(connect=runtime,
        authorize=lambda *args, **kwargs: calls.append("authorize"),
        check_drained=lambda *args, **kwargs: calls.append("drain"),
        host_lease=lease)
    return consumer, calls


def test_default_and_exact_holder_preserve_empty_delivery(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    default, calls = _consumer(runtime)
    assert default.run_once(org_id=org, project_id=project) is None
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    assert lease.acquire() == 1
    guarded, guarded_calls = _consumer(runtime, lease)
    assert guarded.run_once(org_id=org, project_id=project) is None
    assert calls == guarded_calls == []


def test_absent_stale_expired_and_wrong_scope_never_enter_delivery(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    guarded, calls = _consumer(runtime, lease)
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_INPUT_DIFFERS"):
        guarded.run_once(org_id=org, project_id=project)
    assert lease.acquire() == 1
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_INPUT_DIFFERS"):
        guarded.run_once(org_id=org, project_id="other-project")
    lease._epoch += 1  # isolated stale-holder injection
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        guarded.run_once(org_id=org, project_id=project)
    lease._epoch -= 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        guarded.run_once(org_id=org, project_id=project)
    assert calls == []
