"""Disposable-PG Stage entry fence; no real configuration request is submitted."""

import psycopg
import pytest

from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
from aos_api.extension_runtime.configuration_stage_consumer import ConfigurationStageConsumer
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections


def _consumer(runtime, lease=None):
    authority = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(
            installation_store=PostgresInstallationStore(connect_factory=runtime)))
    return ConfigurationStageConsumer(connect=runtime, authorize=authority, host_lease=lease)


def test_default_and_current_holder_use_stage_transaction(fence_case):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    assert _consumer(runtime).run_once(org_id=org, project_id=project) is None
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    assert lease.acquire() == 1
    assert _consumer(runtime, lease).run_once(org_id=org, project_id=project) is None


def test_unacquired_stale_expired_and_wrong_scope_block_stage(fence_case):
    admin_dsn, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, runtime = _connections(directory_dsn, runtime_dsn)
    lease = OptInHostLease(connect=directory, scope=TenantScope(org, project))
    consumer = _consumer(runtime, lease)
    with pytest.raises(HostLeaseBlocked, match='HOST_LEASE_WORKER_FENCE_INPUT_DIFFERS'):
        consumer.run_once(org_id=org, project_id=project)
    assert lease.acquire() == 1
    with pytest.raises(HostLeaseBlocked, match='HOST_LEASE_WORKER_FENCE_INPUT_DIFFERS'):
        consumer.run_once(org_id=org, project_id='other-project')
    lease._epoch += 1  # isolated fault injection: stale holder
    with pytest.raises(HostLeaseBlocked, match='HOST_LEASE_WORKER_FENCE_REJECTED'):
        consumer.run_once(org_id=org, project_id=project)
    lease._epoch -= 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(HostLeaseBlocked, match='HOST_LEASE_WORKER_FENCE_REJECTED'):
        consumer.run_once(org_id=org, project_id=project)


def test_constructor_rejects_non_exact_lease(fence_case):
    _, _, runtime_dsn, _, _, _ = fence_case
    _, runtime = _connections(runtime_dsn, runtime_dsn)
    with pytest.raises(TypeError, match='four-source'):
        _consumer(runtime, object())
