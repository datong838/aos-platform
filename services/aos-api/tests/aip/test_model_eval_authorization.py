"""Model first-Eval preflight cannot grant ordinary runtime or provider access."""

from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import (
    ModelEvalCandidate, ModelModality, ModelPriceSnapshotRevision,
    ModelRuntimeLifecycle, ProviderEndpointProfile, ProviderInstanceRevision,
    RegisteredModelRevision,
)
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_eval_authorization import ModelEvalPreflight
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeConflict, canonical_hash,
    evaluation_candidate_ref,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 10, 2, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
TENANT = TenantContext(org_id="org-org", project_id="dev-project")


def ref(kind, name, digest):
    return VersionedAssetRef(assetType=kind, assetId=name, revision=1, contentHash=digest)


class CurrentCandidateStore:
    def __init__(self):
        self.model = RegisteredModelRevision(
            tenant=TENANT, registeredModelId="m", revision=1, contentHash="1" * 64,
            provider=ref("ProviderInstanceRevision", "p", "2" * 64),
            providerModelId="m", inputModalities=[ModelModality.TEXT],
            outputModalities=[ModelModality.TEXT], capabilities=["text"],
            contextWindow=1024, quotaPolicyRef=ref("QuotaPolicyRevision", "q", "3" * 64),
            budgetPolicyRef=ref("BudgetPolicyRevision", "b", "4" * 64),
            priceSnapshotRef=ref("ModelPriceSnapshotRevision", "price", "5" * 64),
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy="owner", createdAt=NOW,
        )
        self.provider = ProviderInstanceRevision(
            tenant=TENANT, providerInstanceId="p", revision=1, contentHash="2" * 64,
            pluginRef=ref("ProviderPluginRevision", "plugin", "6" * 64),
            endpointProfile=ProviderEndpointProfile(
                baseUrl="https://provider.invalid", region="cn", timeoutMs=1000),
            secretRef="vault://aos/eval", secretVersion="1",
            egressPolicyRef=ref("EgressPolicyRevision", "egress", "7" * 64),
            dataClassificationPolicyRef=ref("DataClassificationPolicyRevision", "data", "8" * 64),
            lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy="owner", createdAt=NOW,
        )
        self.price = ModelPriceSnapshotRevision(
            tenant=TENANT, priceSnapshotId="price", revision=1,
            contentHash="5" * 64, currency="CNY", inputTokenPrice=0.01,
            outputTokenPrice=0.02, tokenUnit=1000, effectiveFrom=NOW,
            lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy="owner", createdAt=NOW,
        )
        self.head_version = 7

    def list_eval_candidates(self, scope):
        if scope != SCOPE:
            return []
        target = evaluation_candidate_ref(self.model.model_copy(update={
            "revision": 2, "lifecycle": ModelRuntimeLifecycle.ACTIVE,
            "eval_gate_ref": None,
        }))
        return [ModelEvalCandidate(
            sourceRef=ref("RegisteredModelRevision", "m", self.model.content_hash),
            targetRef=target, expectedHeadVersion=self.head_version,
            sourceLifecycle="validated",
        )]

    def get_model(self, scope, name, revision):
        assert scope == SCOPE and (name, revision) == ("m", 1)
        return self.model

    def get_provider(self, scope, name, revision):
        assert scope == SCOPE and (name, revision) == ("p", 1)
        return self.provider

    def get_price_snapshot(self, scope, name, revision):
        assert scope == SCOPE and (name, revision) == ("price", 1)
        return self.price

    def require_model_governance(self, scope, model, price, *, now):
        assert scope == SCOPE and model == self.model and price == self.price and now == NOW


def test_model_first_eval_preflight_is_exact_but_never_execution_authority(monkeypatch):
    store = CurrentCandidateStore()
    monkeypatch.setattr(AipModelRuntimeResolver, "_health_is_fresh", staticmethod(lambda *_: True))
    candidate = store.list_eval_candidates(SCOPE)[0]
    resolver = AipModelRuntimeResolver(store=store)
    result = resolver.preflight_model_evaluation(
        SCOPE, candidate.source_ref, candidate.target_ref,
        expected_head_version=7, now=NOW)
    assert result.source_ref == candidate.source_ref
    assert result.target_ref == candidate.target_ref
    assert result.provider_ref == store.model.provider
    assert result.price_ref == store.model.price_snapshot_ref
    assert result.purpose == "quality-eval"
    assert result.execution_allowed is False
    assert "eval_approval_missing" in result.blocker_codes
    assert "budget_capacity_unverified" in result.blocker_codes
    with pytest.raises(ValueError):
        ModelEvalPreflight.model_validate({
            **result.model_dump(mode="json", by_alias=True), "executionAllowed": True,
        })
    with pytest.raises(ValueError):
        ModelEvalPreflight.model_validate({
            **result.model_dump(mode="json", by_alias=True), "purpose": "business-runtime",
        })


@pytest.mark.parametrize("drift", ["head", "source", "target", "tenant"])
def test_model_first_eval_preflight_rejects_unmatched_current_candidate(drift):
    store = CurrentCandidateStore()
    candidate = store.list_eval_candidates(SCOPE)[0]
    source, target, head, scope = candidate.source_ref, candidate.target_ref, 7, SCOPE
    if drift == "head":
        head += 1
    elif drift == "source":
        source = source.model_copy(update={"content_hash": "0" * 64})
    elif drift == "target":
        target = target.model_copy(update={"content_hash": "0" * 64})
    else:
        scope = TenantScope("dev-org", "dev-project")
    with pytest.raises(ValueError):
        AipModelRuntimeResolver(store=store).preflight_model_evaluation(
            scope, source, target, expected_head_version=head, now=NOW)


@pytest.mark.parametrize("drift,blocker", [
    ("provider", "provider_not_active"),
    ("provider_hash", "provider_drifted"),
    ("price", "model_price_snapshot_not_active"),
    ("price_hash", "model_price_snapshot_drifted"),
    ("governance", "model_governance_policy_blocked"),
    ("health", "provider_health_unavailable_or_stale"),
])
def test_model_first_eval_preflight_retains_dependency_blockers(monkeypatch, drift, blocker):
    store = CurrentCandidateStore()
    if drift == "provider":
        store.provider = store.provider.model_copy(update={"lifecycle": ModelRuntimeLifecycle.SUSPENDED})
    elif drift == "provider_hash":
        store.provider = store.provider.model_copy(update={"content_hash": "0" * 64})
    elif drift == "price":
        store.price = store.price.model_copy(update={"lifecycle": ModelRuntimeLifecycle.SUSPENDED})
    elif drift == "price_hash":
        store.price = store.price.model_copy(update={"content_hash": "0" * 64})
    elif drift == "governance":
        from aos_api.aip_model_runtime_store import ModelRuntimeDependencyBlocked
        def reject(*args, **kwargs):
            raise ModelRuntimeDependencyBlocked("governance unavailable")
        store.require_model_governance = reject
    monkeypatch.setattr(AipModelRuntimeResolver, "_health_is_fresh",
                        staticmethod(lambda *_: drift != "health"))
    candidate = store.list_eval_candidates(SCOPE)[0]
    result = AipModelRuntimeResolver(store=store).preflight_model_evaluation(
        SCOPE, candidate.source_ref, candidate.target_ref,
        expected_head_version=7, now=NOW)
    assert blocker in result.blocker_codes
    assert result.execution_allowed is False


def _canonical_model_candidate():
    model = CurrentCandidateStore().model
    body = model.model_dump(mode="json", by_alias=True)
    content = {key: value for key, value in body.items()
               if key not in AipModelRuntimeStore._META_FIELDS}
    model = model.model_copy(update={"content_hash": canonical_hash(content)})
    source = ref("RegisteredModelRevision", model.registered_model_id, model.content_hash)
    target = evaluation_candidate_ref(model.model_copy(update={
        "revision": 2, "lifecycle": ModelRuntimeLifecycle.ACTIVE,
        "eval_gate_ref": None,
    }))
    row = {"version": 7, "asset_id": model.registered_model_id,
           "revision": model.revision, "content_hash": model.content_hash,
           "lifecycle": model.lifecycle.value,
           "payload": model.model_dump(mode="json", by_alias=True)}
    return source, target, row


class LockedCandidateConnection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.row


def test_model_eval_current_candidate_is_rechecked_under_caller_head_lock():
    source, target, row = _canonical_model_candidate()
    conn = LockedCandidateConnection(row)
    candidate = AipModelRuntimeStore().require_current_model_eval_candidate_for_update(
        conn, SCOPE, source, target, expected_head_version=7)
    assert candidate.source_ref == source
    assert candidate.target_ref == target
    assert candidate.expected_head_version == 7
    assert len(conn.calls) == 1
    assert "FOR UPDATE OF h" in conn.calls[0][0]
    assert conn.calls[0][1] == (*SCOPE.key, source.asset_id, source.revision)


@pytest.mark.parametrize("drift", ["missing", "head", "source", "target", "tenant", "row_hash", "payload_hash", "lifecycle"])
def test_model_eval_locked_candidate_rejects_drift(drift):
    source, target, row = _canonical_model_candidate()
    scope, expected = SCOPE, 7
    if drift == "missing":
        row = None
    elif drift == "head":
        expected = 8
    elif drift == "source":
        source = source.model_copy(update={"content_hash": "0" * 64})
    elif drift == "target":
        target = target.model_copy(update={"content_hash": "0" * 64})
    elif drift == "tenant":
        scope = TenantScope("dev-org", "dev-project")
    elif drift == "row_hash":
        row["content_hash"] = "0" * 64
    elif drift == "payload_hash":
        row["payload"]["providerModelId"] = "tampered-model"
    else:
        row["lifecycle"] = "suspended"
    with pytest.raises(ModelRuntimeConflict):
        AipModelRuntimeStore().require_current_model_eval_candidate_for_update(
            LockedCandidateConnection(row), scope, source, target,
            expected_head_version=expected)
