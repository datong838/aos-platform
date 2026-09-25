"""Disposable-PG top-to-bottom metadata lease, never a Store effect."""

import pytest

from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.extension_runtime.host_lease import HostLeaseBlocked, OptInHostLease
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c5i_host_lease_pg import host_lease_case
from test_a0v_w5c5k_worker_fence_pg import fence_case
from test_a0v_w5c5l_preparation_fence_pg import _connections
from test_a0v_w5c5s_metadata_fence_role_pg import _metadata_connector


def _completion(monkeypatch, connect, lease=None):
    claims = object.__new__(PipelineSourceClaimOwner)
    store = object.__new__(EcomConsistencyStore)
    for path in (
        'aos_api.pipeline_snapshot_group_object_executor.PipelineSnapshotGroupRelationshipJournal',
        'aos_api.pipeline_snapshot_group_link_executor.PipelineSnapshotGroupLinkCommandJournal',
        'aos_api.pipeline_snapshot_group_retirement_executor.PipelineSnapshotGroupRetirementJournal',
        'aos_api.pipeline_snapshot_group_completion.PipelineSnapshotGroupProjectionOwner',
        'aos_api.pipeline_snapshot_group_completion.RecoverableStoreAttemptOwner',
    ):
        monkeypatch.setattr(path, lambda **_: object())
    return PipelineSnapshotGroupCompletion(claims=claims, store=store,
        connect=connect, eng=object(), host_lease=lease)


def _chain(completion):
    retirement = completion._retirement
    link = retirement._links
    objects = link._objects
    return retirement, link, objects, objects._single._ingress


def test_default_and_exact_type(fence_case, monkeypatch):
    _, _, runtime_dsn, _, _, _ = fence_case
    connect = _metadata_connector(runtime_dsn)
    completion = _completion(monkeypatch, connect)
    retirement, link, objects, ingress = _chain(completion)
    assert completion._host_lease is objects._host_lease is ingress._host_lease is None
    with pytest.raises(TypeError, match='exact snapshot Link Host lease'):
        ControlledSnapshotGroupLinkExecutor(claims=None, store=None, connect=connect,
            eng=object(), host_lease=object())
    with pytest.raises(TypeError, match='exact snapshot Retirement Host lease'):
        ControlledSnapshotGroupRetirementExecutor(claims=None, store=None, connect=connect,
            eng=object(), host_lease=object())
    assert retirement._links is link


def test_same_holder_fences_top_to_bottom(fence_case, monkeypatch):
    _, directory_dsn, runtime_dsn, org, project, _ = fence_case
    directory, _ = _connections(directory_dsn, runtime_dsn)
    scope = TenantScope(org, project)
    lease = OptInHostLease(connect=directory, scope=scope)
    completion = _completion(monkeypatch, _metadata_connector(runtime_dsn), lease)
    retirement, link, objects, ingress = _chain(completion)
    assert completion._host_lease is objects._host_lease is ingress._host_lease is lease
    with pytest.raises(HostLeaseBlocked, match='INPUT_DIFFERS'):
        with completion._transaction(scope):
            raise AssertionError('Completion body must not run')
    assert lease.acquire() == 1
    for owner in (completion, retirement, link, objects, ingress):
        with owner._transaction(scope):
            pass
    lease._epoch += 1
    for owner in (completion, retirement, link, objects, ingress):
        with pytest.raises(HostLeaseBlocked, match='REJECTED'):
            with owner._transaction(scope):
                raise AssertionError('Metadata body must not run')
