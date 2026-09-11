from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle, ModelRuntimeReadiness
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeDependencyBlocked
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from test_aip_model_runtime_resolver import ReadyRuntimeStore, SCOPE, NOW
from test_aip_development_model_binding import assembly as governance_assembly


def setup_store():
    fixtures = ReadyRuntimeStore()
    model = fixtures.get_model()
    price = fixtures.get_price_snapshot()
    governance, _, budget, _ = governance_assembly()
    auth = budget.development_cost_authorization
    auth.provider = model.provider
    auth.provider_model_id = model.provider_model_id
    governance.require_exact_active = lambda *_args, **_kwargs: budget
    store = object.__new__(AipModelRuntimeStore)
    store._governance_policy_store = governance
    store.get_price_snapshot = lambda *_: price
    store._eval_authority_store = SimpleNamespace(require_exact_passed=lambda *_a, **_k: None)
    writes = []
    store._publish = lambda *args: writes.append(args)
    return store, model, price, budget, writes


def test_publish_rejects_price_authorization_mismatch_before_write():
    store, model, price, budget, writes = setup_store()
    price.development_cost_authorization = budget.development_cost_authorization.model_copy(update={'approval_ref': 'wrong'})
    with pytest.raises(ModelRuntimeDependencyBlocked, match='price authorization'):
        store.publish_model(SCOPE, 'test', 'key', model)
    assert writes == []


@pytest.mark.parametrize('change', ['hash', 'tenant', 'future', 'expired', 'inactive'])
def test_active_model_publish_requires_current_exact_price(change):
    store, model, price, _, writes = setup_store()
    if change == 'hash': price.content_hash = 'f'*64
    if change == 'tenant': price.tenant = price.tenant.model_copy(update={'org_id':'dev-org'})
    if change == 'future': price.effective_from = datetime.now(UTC)+timedelta(days=1)
    if change == 'expired': price.effective_until = datetime.now(UTC)-timedelta(seconds=1)
    if change == 'inactive': price.lifecycle = ModelRuntimeLifecycle.DRAFT
    with pytest.raises(ModelRuntimeDependencyBlocked):
        store.publish_model(SCOPE, 'test', 'key', model)
    assert writes == []


def test_resolver_rechecks_price_authorization_in_owner(monkeypatch):
    owner, _, price, budget, _ = setup_store()
    price.development_cost_authorization = budget.development_cost_authorization.model_copy(update={'approval_ref':'wrong'})
    fixtures = ReadyRuntimeStore()
    fixtures.get_price_snapshot = lambda *_: price
    fixtures.require_model_governance = owner.require_model_governance
    monkeypatch.setattr(AipModelRuntimeResolver, '_gate_passed', staticmethod(lambda *_: True))
    monkeypatch.setattr(AipModelRuntimeResolver, '_health_is_fresh', staticmethod(lambda *_: True))
    result = AipModelRuntimeResolver(fixtures).resolve(SCOPE, 'route', now=NOW)
    assert result.readiness is ModelRuntimeReadiness.BLOCKED
    assert 'model_governance_policy_blocked' in result.blocker_codes
    assert result.selected_model is None


def test_staged_model_keeps_staged_price_configuration_path():
    store, model, price, _, writes = setup_store()
    model.lifecycle = ModelRuntimeLifecycle.VALIDATED
    price.lifecycle = ModelRuntimeLifecycle.VALIDATED
    store.publish_model(SCOPE, 'test', 'key', model)
    assert len(writes) == 1


def test_authorization_uses_resolver_decision_time():
    store, model, price, budget, _ = setup_store()
    price.development_cost_authorization = budget.development_cost_authorization
    later = budget.development_cost_authorization.effective_until
    with pytest.raises(ModelRuntimeDependencyBlocked, match='cover model'):
        store.require_model_governance(SCOPE, model, price, now=later)


@pytest.mark.parametrize('state', ['active', 'suspended', 'revoked'])
def test_real_deferred_price_dto_obeys_owner_lifecycle_and_authorization(state):
    from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision
    owner, model, _, budget, writes = setup_store()
    auth = budget.development_cost_authorization
    ref = model.price_snapshot_ref
    price = ModelPriceSnapshotRevision(
        tenant=model.tenant, priceSnapshotId=ref.asset_id, revision=ref.revision,
        contentHash=ref.content_hash, currency='CNY', lifecycle=state,
        effectiveFrom=auth.effective_from, effectiveUntil=auth.effective_until,
        createdBy='test', createdAt=auth.effective_from,
        developmentCostAuthorization=auth,
    )
    price = ModelPriceSnapshotRevision.model_validate_json(price.model_dump_json(by_alias=True))
    owner.get_price_snapshot = lambda *_: price
    if state != 'active':
        with pytest.raises(ModelRuntimeDependencyBlocked, match='not effective'):
            owner.publish_model(SCOPE, 'test', 'inactive-price', model)
        assert writes == []
        return
    owner.publish_model(SCOPE, 'test', 'active-price', model)
    assert len(writes) == 1
    budget.development_cost_authorization = None
    with pytest.raises(ModelRuntimeDependencyBlocked, match='price authorization'):
        owner.publish_model(SCOPE, 'test', 'withdrawn-authorization', model)
    assert len(writes) == 1


def test_deferred_old_price_ref_cannot_survive_current_price_revocation():
    owner, model, price, budget, writes = setup_store()
    price.development_cost_authorization = budget.development_cost_authorization
    revoked = SimpleNamespace(**vars(price)) if not hasattr(price, 'model_copy') else price.model_copy(deep=True)
    revoked.revision = price.revision + 1
    revoked.lifecycle = ModelRuntimeLifecycle.REVOKED
    owner.get_price_snapshot = lambda _scope, _id, revision=None: price if revision is not None else revoked
    with pytest.raises(ModelRuntimeDependencyBlocked, match='current'):
        owner.publish_model(SCOPE, 'test', 'old-price', model)
    assert writes == []
