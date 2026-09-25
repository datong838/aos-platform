"""No-effect structural inventory: a partial Attempt fence is not full Store authority."""

import inspect

from aos_api.extension_runtime.recoverable_store_attempt import RecoverableStoreAttemptOwner
from aos_api.pipeline_controlled_executor import ControlledSnapshotExecutor
from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor
from aos_api.pipeline_snapshot_group_object_executor import ControlledSnapshotGroupObjectExecutor
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor


def test_attempt_claim_commits_before_execution_and_is_not_host_lease_wired():
    body = inspect.getsource(PipelineSnapshotGroupCompletion.complete)
    assert body.index('attempt = self._attempts.claim(') < body.index('with attempt:')
    assert 'self._attempts = RecoverableStoreAttemptOwner(connect=connect)' in inspect.getsource(
        PipelineSnapshotGroupCompletion.__init__)
    assert 'host_lease: OptInHostLease | None = None' in inspect.getsource(
        RecoverableStoreAttemptOwner.__init__)


def test_completion_transaction_delegation_still_reaches_original_ingress():
    chain = (
        (PipelineSnapshotGroupCompletion, 'self._retirement._transaction(scope)'),
        (ControlledSnapshotGroupRetirementExecutor, 'self._links._transaction(scope)'),
        (ControlledSnapshotGroupLinkExecutor, 'self._objects._transaction(scope)'),
        (ControlledSnapshotGroupObjectExecutor, 'self._single._ingress._transaction(scope)'),
    )
    for owner, expected in chain:
        assert expected in inspect.getsource(owner._transaction)
    ingress = inspect.getsource(ControlledSnapshotIngress._transaction)
    assert 'apply_asset_transaction_scope' in ingress
    assert 'fence_in_transaction' not in ingress
    assert 'consumer_connection' not in ingress


def test_store_effects_cross_multiple_independent_commit_boundaries():
    link = inspect.getsource(ControlledSnapshotGroupLinkExecutor.execute)
    retirement = inspect.getsource(ControlledSnapshotGroupRetirementExecutor.execute)
    single = inspect.getsource(ControlledSnapshotExecutor._finish)
    assert link.index('with self._transaction(scope) as conn:') < link.index(
        'self._store.apply_strict_link_batch(')
    assert retirement.index('with self._transaction(scope) as conn:') < retirement.index(
        'self._store.apply_strict_link_retirement_batch(')
    assert 'finalize_saved_dataset(' in single
    assert 'recover_saved_authoritative_stages(' in single
