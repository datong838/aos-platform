"""Disposable-PG exact lease propagation, no source or Store effect."""

import pytest

from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.pipeline_controlled_executor import ControlledSnapshotExecutor
from aos_api.pipeline_snapshot_group_object_executor import ControlledSnapshotGroupObjectExecutor
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_a0v_w5c5s_metadata_fence_role_pg import _metadata_connector


def _owners():
    return object.__new__(PipelineSourceClaimOwner), object.__new__(EcomConsistencyStore)


def test_exact_type_and_default_propagation(fence_case, monkeypatch):
    _, _, runtime_dsn, _, _, _ = fence_case
    claims, store = _owners()
    connect = _metadata_connector(runtime_dsn)
    monkeypatch.setattr('aos_api.pipeline_snapshot_group_object_executor.PipelineSnapshotGroupRelationshipJournal',
                        lambda **_: object())
    single = ControlledSnapshotExecutor(claims=claims, store=store, connect=connect, eng=object())
    assert single._ingress._host_lease is None
    group = ControlledSnapshotGroupObjectExecutor(claims=claims, store=store, connect=connect, eng=object())
    assert group._host_lease is None and group._single._ingress._host_lease is None
    with pytest.raises(TypeError, match='exact snapshot Single Host lease'):
        ControlledSnapshotExecutor(claims=claims, store=store, connect=connect, eng=object(), host_lease=object())
    with pytest.raises(TypeError, match='exact snapshot Object Host lease'):
        ControlledSnapshotGroupObjectExecutor(claims=claims, store=store, connect=connect, eng=object(), host_lease=object())


def test_same_holder_fences_object_and_internal_single(fence_case, monkeypatch):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    claims, store = _owners()
    monkeypatch.setattr('aos_api.pipeline_snapshot_group_object_executor.PipelineSnapshotGroupRelationshipJournal',
                        lambda **_: object())
    group = ControlledSnapshotGroupObjectExecutor(claims=claims, store=store,
        connect=_metadata_connector(runtime_dsn), eng=object(), host_lease=lease)
    assert group._host_lease is group._single._ingress._host_lease is lease
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with group._single._ingress._transaction(scope):
            raise AssertionError('Single body must not run')
    assert lease.acquire() == 1
    with group._transaction(scope):
        pass
    with group._single._ingress._run_transaction(scope, run_id='no-schedule-binding'):
        pass
    lease._epoch += 1
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with group._transaction(scope):
            raise AssertionError('Object body must not run')
    with pytest.raises(HostLeaseBlocked, match='REJECTED'):
        with group._single._ingress._transaction(scope):
            raise AssertionError('Single body must not run')
