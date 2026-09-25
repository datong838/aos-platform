"""No-effect lifetime inventory; not a real Store effect authorization."""

import inspect
from pathlib import Path

from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.extension_runtime.host_lease import OptInHostLease
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor


MIGRATION = (Path(__file__).resolve().parents[2] / 'alembic' / 'versions'
             / 'a0v_094_host_lease_worker_fence.py')


def test_lease_is_bounded_but_worker_guard_takes_share_locks():
    lease = inspect.getsource(OptInHostLease.__init__)
    guard = inspect.getsource(OptInHostLease.fence_in_transaction)
    sql = MIGRATION.read_text()
    assert '5 <= ttl_seconds <= 30' in lease
    assert 'renew_interval_seconds < ttl_seconds // 2' in lease
    assert 'FOR SHARE' in sql
    assert 'clock_timestamp()' in sql
    assert 'expires_at<=v_now' in sql
    assert 'self._connect()' not in guard


def test_store_effect_transactions_have_return_guards_but_no_total_duration_bound():
    for method in (EcomConsistencyStore._apply_batch, EcomConsistencyStore.update_derived_metrics):
        body = inspect.getsource(method)
        assert 'with process_lock, self._engine.begin() as conn:' in body
        assert body.count('_fence_store_transaction(') == 3
        assert 'transaction_timeout' not in body
        assert 'statement_timeout' not in body
        assert 'lock_timeout' not in body


def test_group_callers_still_do_not_pass_lease_to_independent_store():
    for owner in (ControlledSnapshotGroupLinkExecutor, ControlledSnapshotGroupRetirementExecutor):
        body = inspect.getsource(owner.execute)
        assert 'self._store.apply_strict_link_' in body
        assert 'host_lease=' not in body
        assert body.index('prepared = self._') < body.index('self._store.apply_strict_link_')
