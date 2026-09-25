"""No-effect audit: metadata lease does not flow into independent Store commits."""

import inspect

from aos_api.ec_ingress_recovery import recover_saved_authoritative_stages, resume_prepared_derived
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor


def test_single_base_and_derived_still_submit_independent_unfenced_store_effects():
    base = inspect.getsource(recover_saved_authoritative_stages)
    derived = inspect.getsource(resume_prepared_derived)
    assert base.index('with connection_factory(scope) as conn:') < base.index('store.apply_batch(command)')
    assert base.index('store.apply_batch(command)') < base.index('latest_parent = _bound_parent')
    assert 'host_lease' not in inspect.signature(recover_saved_authoritative_stages).parameters
    assert 'host_lease' not in inspect.signature(resume_prepared_derived).parameters
    assert 'store.apply_batch(command)' in base
    assert 'store.update_derived_metrics(\n            item, expected_base=' in derived
    assert derived.index('latest_parent, latest_saved = current()') < derived.index(
        'store.update_derived_metrics(')


def test_link_and_retirement_store_effects_follow_preparation_and_precede_readback():
    for owner, effect, readback in (
        (ControlledSnapshotGroupLinkExecutor, 'self._store.apply_strict_link_batch(saved.command)',
         'GROUP_LINK_PREPARATION_CHANGED'),
        (ControlledSnapshotGroupRetirementExecutor,
         'self._store.apply_strict_link_retirement_batch(saved.command)',
         'RETIREMENT_PREPARATION_CHANGED'),
    ):
        body = inspect.getsource(owner.execute)
        assert 'host_lease' not in inspect.signature(owner.execute).parameters
        assert body.index('prepared = self._') < body.index(effect)
        assert body.index(effect) < body.rindex('with self._transaction(scope) as conn:')
        assert readback in body
        assert 'host_lease=' not in body


def test_caller_deadline_checks_do_not_make_store_commit_atomic_with_metadata():
    for owner in (ControlledSnapshotGroupLinkExecutor, ControlledSnapshotGroupRetirementExecutor):
        body = inspect.getsource(owner.execute)
        assert body.index('_check_active(**active)') < body.index('self._store.apply_strict_link_')
        assert body.index('self._store.apply_strict_link_') < body.rindex('_check_active(**active)')
    derived = inspect.getsource(resume_prepared_derived)
    assert 'for item in commands:' in derived
    assert derived.index('for item in commands:') < derived.index('store.update_derived_metrics(')
    assert 'Each derived submission\n    owns its existing receipt transaction' in derived
