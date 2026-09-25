"""No-effect design inventory; opt-in Store fence is not implemented yet."""

import ast
import inspect
import textwrap

from aos_api.ecom_consistency_store import EcomConsistencyStore


EFFECT_APIS = (
    EcomConsistencyStore.apply_batch,
    EcomConsistencyStore.apply_strict_link_batch,
    EcomConsistencyStore.apply_strict_link_retirement_batch,
    EcomConsistencyStore.update_derived_metrics,
)


def _returns(method):
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    return sum(isinstance(node, ast.Return) for node in ast.walk(tree))


def test_all_four_effect_apis_expose_default_off_opt_in_lease():
    assert len(EFFECT_APIS) == 4
    for method in EFFECT_APIS:
        param = inspect.signature(method).parameters['host_lease']
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is None
    assert inspect.signature(EcomConsistencyStore._apply_batch).parameters['host_lease'].default is None


def test_base_and_derived_both_have_replay_and_new_write_commit_exits():
    for method in (EcomConsistencyStore._apply_batch, EcomConsistencyStore.update_derived_metrics):
        body = inspect.getsource(method)
        assert 'with process_lock, self._engine.begin() as conn:' in body
        assert body.index('_apply_transaction_scope(') < body.index('self._lock_idempotency_key(')
        assert _returns(method) == 2
    base = inspect.getsource(EcomConsistencyStore._apply_batch)
    assert base.index('replay = self._get_receipt(') < base.index('return BatchResult.model_validate(saved)')
    assert base.index('insert(ecom_ingest_receipt)') < base.rindex('return result')
    derived = inspect.getsource(EcomConsistencyStore.update_derived_metrics)
    assert derived.index('if receipt is not None:') < derived.index('return DerivedMetricResult.model_validate(saved)')
    assert derived.index('ecom_derived_receipt') < derived.rindex('return result')
    assert base.count('_fence_store_transaction(') == 3
    assert derived.count('_fence_store_transaction(') == 3
