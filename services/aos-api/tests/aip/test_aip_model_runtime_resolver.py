from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import (
    ModelModality, ModelRouteCandidate, ModelRouteRevision, ModelRuntimeLifecycle,
    ModelRuntimeReadiness, ProviderEndpointProfile, ProviderInstanceRevision,
    RegisteredModelRevision, RouteStrategy, RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 13, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
TENANT = TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id)


def ref(kind: str, asset_id: str, digest: str) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=1, contentHash=digest)


class EmptyRuntimeStore:
    def get_route(self, scope, route_id):
        return ModelRouteRevision(
            tenant=TENANT, routeId=route_id, revision=1, contentHash="1" * 64,
            taskTypes=["copy.generate"], requiredInputModality=ModelModality.TEXT,
            requiredOutputModality=ModelModality.TEXT, requiredCapabilities=["structured_output"],
            candidates=[ModelRouteCandidate(model=ref("RegisteredModelRevision", "model", "2" * 64))],
            strategy=RouteStrategy.FAILOVER,
            runtimePolicyRef=ref("RuntimePolicyRevision", "policy", "3" * 64),
            evalGateRef=ref("EvalGateDecision", "gate", "4" * 64),
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy="test", createdAt=NOW,
        )

    def get_policy(self, *args):
        from aos_api.aip_model_runtime_store import ModelRuntimeNotFound
        raise ModelRuntimeNotFound("missing")

    def get_model(self, *args):
        from aos_api.aip_model_runtime_store import ModelRuntimeNotFound
        raise ModelRuntimeNotFound("missing")


class ReadyRuntimeStore(EmptyRuntimeStore):
    def get_route(self, scope, route_id):
        return super().get_route(scope, route_id).model_copy(update={"lifecycle": ModelRuntimeLifecycle.ACTIVE})

    def get_policy(self, *args):
        return RuntimePolicyRevision(
            tenant=TENANT, policyId="policy", revision=1, contentHash="3" * 64,
            networkPolicyRef=ref("NetworkPolicyRevision", "network", "5" * 64),
            egressPolicyRef=ref("EgressPolicyRevision", "egress", "6" * 64),
            dataClassificationPolicyRef=ref("DataClassificationPolicyRevision", "classification", "7" * 64),
            quotaPolicyRef=ref("QuotaPolicyRevision", "quota", "8" * 64),
            budgetPolicyRef=ref("BudgetPolicyRevision", "budget", "9" * 64),
            deadlineMs=1000, maxAttempts=1, unknownUsageBehavior="block", unknownPriceBehavior="block",
            killSwitchEnabled=False, lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy="test", createdAt=NOW,
        )

    def get_model(self, *args):
        return RegisteredModelRevision(
            tenant=TENANT, registeredModelId="model", revision=1, contentHash="2" * 64,
            provider=ref("ProviderInstanceRevision", "provider", "a" * 64), providerModelId="model-test",
            inputModalities=[ModelModality.TEXT], outputModalities=[ModelModality.TEXT],
            capabilities=["structured_output"], contextWindow=4096,
            quotaPolicyRef=ref("QuotaPolicyRevision", "quota", "8" * 64),
            budgetPolicyRef=ref("BudgetPolicyRevision", "budget", "9" * 64),
            priceSnapshotRef=ref("ModelPriceSnapshotRevision", "price", "b" * 64),
            evalGateRef=ref("EvalGateDecision", "model-gate", "c" * 64),
            lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy="test", createdAt=NOW,
        )

    def get_provider(self, *args):
        return ProviderInstanceRevision(
            tenant=TENANT, providerInstanceId="provider", revision=1, contentHash="a" * 64,
            pluginRef=ref("ProviderPluginRevision", "plugin", "d" * 64),
            endpointProfile=ProviderEndpointProfile(baseUrl="https://provider.invalid", region="cn", timeoutMs=1000),
            secretRef="vault://aos/test", secretVersion="1",
            egressPolicyRef=ref("EgressPolicyRevision", "egress", "6" * 64),
            dataClassificationPolicyRef=ref("DataClassificationPolicyRevision", "classification", "7" * 64),
            lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy="test", createdAt=NOW,
        )

def test_resolver_honestly_blocks_non_active_zero_dependency_route(monkeypatch) -> None:
    monkeypatch.setattr(AipModelRuntimeResolver, "_gate_passed", staticmethod(lambda *_: False))
    resolver = AipModelRuntimeResolver(store=EmptyRuntimeStore())
    result = resolver.resolve(SCOPE, "route-copy", now=NOW)
    assert result.readiness is ModelRuntimeReadiness.BLOCKED
    assert result.selected_model is None and result.selected_provider is None
    assert result.blocker_codes == [
        "route_not_active", "runtime_policy_unavailable",
        "route_eval_gate_not_passed", "model_unavailable",
    ]


def test_real_tenant_with_no_route_fails_closed() -> None:
    from aos_api.aip_model_runtime_store import ModelRuntimeNotFound
    resolver = AipModelRuntimeResolver()
    try:
        resolver.resolve(SCOPE, "does-not-exist", now=NOW)
    except ModelRuntimeNotFound as exc:
        assert "model_route" in str(exc)
    else:
        raise AssertionError("missing route must not resolve from defaults or another tenant")


def test_resolver_returns_exact_ready_selection_only_when_all_gates_pass(monkeypatch) -> None:
    monkeypatch.setattr(AipModelRuntimeResolver, "_gate_passed", staticmethod(lambda *_: True))
    monkeypatch.setattr(AipModelRuntimeResolver, "_health_is_fresh", staticmethod(lambda *_: True))
    result = AipModelRuntimeResolver(store=ReadyRuntimeStore()).resolve(SCOPE, "route-copy", now=NOW)
    assert result.readiness is ModelRuntimeReadiness.READY
    assert result.selected_model.asset_id == "model"
    assert result.selected_provider.asset_id == "provider"
    assert result.blocker_codes == []
