"""No-effect inventory: metadata Host fences do not make Store effects atomic."""

import inspect

from aos_api.ec_ingress_dataset import finalize_saved_dataset
from aos_api.ec_ingress_recovery import recover_saved_authoritative_stages, resume_prepared_derived
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor


def test_single_base_and_derived_store_effects_follow_independent_metadata_checks():
    base = inspect.getsource(recover_saved_authoritative_stages)
    assert base.index('with connection_factory(scope) as conn:') < base.index('store.apply_batch(command)')
    assert base.index('store.apply_batch(command)') < base.index('latest_parent = _bound_parent')
    derived = inspect.getsource(resume_prepared_derived)
    assert derived.index('parent, saved = current()') < derived.index('store.update_derived_metrics(')
    assert derived.index('store.update_derived_metrics(') < derived.rindex('latest_parent, latest_saved = current()')


def test_link_and_retirement_store_effects_follow_preparation_commit():
    for owner, effect in (
        (ControlledSnapshotGroupLinkExecutor, 'self._store.apply_strict_link_batch('),
        (ControlledSnapshotGroupRetirementExecutor, 'self._store.apply_strict_link_retirement_batch('),
    ):
        body = inspect.getsource(owner.execute)
        assert body.index('with self._transaction(scope) as conn:') < body.index(effect)
        assert body.index(effect) < body.rindex('with self._transaction(scope) as conn:')


def test_store_owns_a_separate_receipt_transaction_with_default_off_host_lease():
    body = inspect.getsource(EcomConsistencyStore._apply_batch)
    assert 'with process_lock, self._engine.begin() as conn:' in body
    assert body.index('replay = self._get_receipt(') < body.index('insert(ecom_ingest_receipt)')
    assert body.index('insert(ecom_ingest_receipt)') < body.index('return result')
    for method in (EcomConsistencyStore.apply_batch,
                   EcomConsistencyStore.apply_strict_link_batch,
                   EcomConsistencyStore.apply_strict_link_retirement_batch,
                   EcomConsistencyStore.update_derived_metrics):
        assert inspect.signature(method).parameters['host_lease'].default is None


def test_dataset_receipt_commit_precedes_in_memory_publication():
    body = inspect.getsource(finalize_saved_dataset)
    assert body.index('INSERT INTO {}(org_id,project_id,run_id,payload_hash,payload)') < body.index(
        'eng.get_dataset(scope,item[\'rid\'])')
    assert body.index('eng.get_dataset(scope,item[\'rid\'])') < body.index('eng.add_build(')
