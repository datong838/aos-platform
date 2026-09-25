"""No-effect audit: stalled closure and Store effects are separate authorities."""

import inspect
from pathlib import Path

from aos_api.ecom_consistency_store import EcomConsistencyStore, _apply_transaction_scope
from aos_api.pipeline_snapshot_stalled_group_closure import StalledSnapshotGroupClosureService


MIGRATION = (Path(__file__).resolve().parents[2] / 'alembic' / 'versions'
             / 'a0v_091_snapshot_stalled_group_closure.py')


def test_stalled_closure_owns_serializable_maintainer_transaction_and_receipt():
    service = inspect.getsource(StalledSnapshotGroupClosureService)
    sql = MIGRATION.read_text()
    assert 'IsolationLevel.SERIALIZABLE' in service
    assert 'consumer_connection(' in service
    assert 'SET LOCAL ROLE aos_extension_maintainer' in service
    assert 'pipeline_snapshot_stalled_group_close_a0v_091' in service
    assert 'pipeline_snapshot_stalled_group_closure_receipt' in service
    assert "current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'" in sql
    assert 'STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS' in sql
    assert '24' in sql


def test_store_effects_own_separate_runtime_transactions_not_closure_connection():
    service = inspect.getsource(StalledSnapshotGroupClosureService.close)
    base = inspect.getsource(EcomConsistencyStore._apply_batch)
    derived = inspect.getsource(EcomConsistencyStore.update_derived_metrics)
    assert 'self._engine.begin() as conn:' in base
    assert 'self._engine.begin() as conn:' in derived
    assert 'SET LOCAL ROLE aos_runtime' in inspect.getsource(_apply_transaction_scope)
    assert 'self._engine' not in service
    assert 'EcomConsistencyStore' not in service
    assert 'conn' not in inspect.signature(EcomConsistencyStore.apply_batch).parameters
    assert 'conn' not in inspect.signature(EcomConsistencyStore.update_derived_metrics).parameters


def test_stalled_closure_receipt_cannot_authorize_store_effect_or_resend():
    service = inspect.getsource(StalledSnapshotGroupClosureService.close)
    sql = MIGRATION.read_text()
    assert "response['businessAccepted']" not in service
    assert 'response["businessAccepted"] is not False' in service
    assert 'ecom_ingest_receipt' not in sql
    assert 'ecom_derived_receipt' not in sql
    assert 'apply_batch(' not in service
