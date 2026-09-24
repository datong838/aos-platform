"""OwnedControlConsumer opt-in outbox fence in disposable PostgreSQL."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer
from aos_api.extension_runtime.preparation_worker import PreparedJob
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


def _job(org, project):
    job = object.__new__(PreparedJob)
    job._tenant_scope = TenantScope(org, project)
    job.plan = SimpleNamespace(installation_id=uuid4(), generation=uuid4())
    return job


def test_owned_claim_finish_use_same_transaction_fence(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    assert lease.acquire() == 1
    consumer = OwnedControlConsumer(connect=runtime, job=_job(org, project),
                                    kind="enable", org_id=org, project_id=project,
                                    host_lease=lease)
    assert consumer._claim() is None
    lease._epoch += 1  # isolated fault injection
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        consumer._claim()
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_REJECTED"):
        consumer._finish(object())


def test_owned_default_and_unacquired_opt_in(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    default = OwnedControlConsumer(connect=runtime, job=_job(org, project),
                                   kind="runtime-verify", org_id=org, project_id=project)
    assert default._claim() is None
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    guarded = OwnedControlConsumer(connect=runtime, job=_job(org, project),
                                   kind="runtime-verify", org_id=org, project_id=project,
                                   host_lease=lease)
    with pytest.raises(HostLeaseBlocked, match="WORKER_FENCE_INPUT_DIFFERS"):
        guarded._claim()
    with pytest.raises(TypeError, match="Host lease scope"):
        OwnedControlConsumer(connect=runtime, job=_job(org, project), kind="enable",
                             org_id=org, project_id=project,
                             host_lease=OptInHostLease(connect=directory,
                                                       scope=TenantScope("other-org", project)))
