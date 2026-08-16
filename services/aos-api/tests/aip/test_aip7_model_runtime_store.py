from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import psycopg
import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import (
    ModelModality,
    ModelPriceSnapshotRevision,
    ModelRouteCandidate,
    ModelRouteRevision,
    ModelRuntimeLifecycle,
    ProviderEndpointProfile,
    ProviderHealthObservation,
    ProviderInstanceRevision,
    RegisteredModelRevision,
    RouteStrategy,
    RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore,
    ModelRuntimeDependencyBlocked,
    ModelRuntimeIdempotencyConflict,
    ModelRuntimeNotFound,
    canonical_hash,
)
from aos_api.aip_eval_authority_store import AipEvalGateDependencyBlocked
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevisionCreate,
)
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevisionCreate,
    QuotaPolicyRevisionCreate,
)
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
CANARY = TenantScope(org_id="dev-org", project_id="dev-project")
TENANT = TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id)
NOW = datetime.now(UTC)
SUFFIX = f"test:aip7-store:{uuid.uuid4().hex}"


def ref(kind: str, asset_id: str, digest: str) -> VersionedAssetRef:
    return VersionedAssetRef(asset_type=kind, asset_id=asset_id, revision=1, content_hash=digest)


def hashed(model: type, payload: dict):
    provisional = model(**payload, contentHash="0" * 64)
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {
        name: value
        for name, value in dumped.items()
        if name not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
    }
    return model(**payload, contentHash=canonical_hash(content))


def rehashed(item, **updates):
    payload = item.model_dump(mode="json", by_alias=True)
    payload.update(updates)
    payload["contentHash"] = "0" * 64
    provisional = type(item).model_validate(payload)
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {
        name: value
        for name, value in dumped.items()
        if name not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
    }
    payload["contentHash"] = canonical_hash(content)
    return type(item).model_validate(payload)


def cleanup() -> None:
    with psycopg.connect(get_dsn()) as conn:
        conn.execute("DELETE FROM aip_model_runtime_receipt WHERE org_id=%s AND project_id=%s AND created_by=%s", (*SCOPE.key, SUFFIX))
        conn.execute("DELETE FROM aip_provider_health_observation WHERE org_id=%s AND project_id=%s AND observation_id LIKE %s", (*SCOPE.key, f"{SUFFIX}%"))
        for kind in ("model_route", "registered_model", "runtime_policy", "provider_instance"):
            id_column = f"{kind}_id"
            conn.execute(
                f"DELETE FROM aip_{kind}_revision WHERE org_id=%s AND project_id=%s AND {id_column} LIKE %s",
                (*SCOPE.key, f"{SUFFIX}%"),
            )
            conn.execute(
                f"DELETE FROM aip_{kind}_head WHERE org_id=%s AND project_id=%s AND {id_column} LIKE %s",
                (*SCOPE.key, f"{SUFFIX}%"),
            )
        conn.commit()


def publish_runtime_guards() -> tuple[VersionedAssetRef, VersionedAssetRef]:
    instant = datetime.now(UTC)
    store = AipRuntimeGuardPolicyStore()
    egress = store.publish_egress(
        SCOPE,
        SUFFIX,
        "guard-egress-1",
        EgressPolicyRevisionCreate(
            policyId=f"{SUFFIX}:egress",
            revision=1,
            environment="development",
            effectiveFrom=instant - timedelta(hours=1),
            effectiveUntil=instant + timedelta(days=30),
            owner=SUFFIX,
            approvalRef="approval:test:aip7-store",
            lifecycle="active",
            allowedSchemes=["https"],
            allowedHosts=["apihub.agnes-ai.com"],
            allowedPorts=[443],
            allowPublicFallback=False,
            unknownDestinationBehavior="block",
            regionState="confirmed",
            region="cn-approved-development",
        ),
    )
    data = store.publish_data_classification(
        SCOPE,
        SUFFIX,
        "guard-data-1",
        DataClassificationPolicyRevisionCreate(
            policyId=f"{SUFFIX}:classification",
            revision=1,
            environment="development",
            effectiveFrom=instant - timedelta(hours=1),
            effectiveUntil=instant + timedelta(days=30),
            owner=SUFFIX,
            approvalRef="approval:test:aip7-store",
            lifecycle="active",
            allowedClassifications=["public_catalog"],
            prohibitedClassifications=[
                "direct_pii", "raw_order_detail", "customer_conversation", "credential",
                "commercial_sensitive", "cross_tenant", "unknown",
            ],
            denyUnknown=True,
            allowDirectPii=False,
            allowCommercialSensitive=False,
            allowCrossTenant=False,
        ),
    )
    return (
        ref("EgressPolicyRevision", egress.policy_id, egress.content_hash),
        ref("DataClassificationPolicyRevision", data.policy_id, data.content_hash),
    )


def publish_model_governance_policies() -> tuple[VersionedAssetRef, VersionedAssetRef]:
    instant = datetime.now(UTC)
    budget = AipBudgetAuthorityStore().publish(
        SCOPE, SUFFIX, "model-budget-revision-1",
        BudgetRevisionCreate(
            budgetId=f"{SUFFIX}:budget-revision", revision=1, environment="development",
            currency="CNY", dailyLimitMinor=500, monthlyLimitMinor=5000,
            alertThresholdPct=80, hardStop=True, unknownUsageBehavior="block",
            effectiveFrom=instant - timedelta(hours=2), effectiveUntil=instant + timedelta(days=60),
            owner=SUFFIX, overBudgetApprover=SUFFIX, lifecycle="active",
        ),
    )
    store = AipModelGovernancePolicyStore()
    quota = store.publish_quota(
        SCOPE, SUFFIX, "model-quota-policy-1",
        QuotaPolicyRevisionCreate(
            policyId=f"{SUFFIX}:quota-policy", revision=1, environment="development",
            effectiveFrom=instant - timedelta(hours=1), effectiveUntil=instant + timedelta(days=30),
            owner=SUFFIX, approvalRef="approval:test:aip7-store", lifecycle="active",
            maxConcurrency=2, maxInputTokens=8000, maxOutputTokens=2000,
            hourlyRequestLimit=50, dailyRequestLimit=200, reservationLeaseSeconds=60,
            overflowBehavior="queue", allowPublicProviderFallback=False, allowAutoScale=False,
        ),
    )
    budget_policy = store.publish_budget(
        SCOPE, SUFFIX, "model-budget-policy-1",
        BudgetPolicyRevisionCreate(
            policyId=f"{SUFFIX}:budget-policy", revision=1, environment="development",
            effectiveFrom=instant - timedelta(hours=1), effectiveUntil=instant + timedelta(days=30),
            owner=SUFFIX, approvalRef="approval:test:aip7-store", lifecycle="active",
            budgetRevisionRef=ref("BudgetRevision", budget.budget_id, budget.content_hash),
            currency="CNY", hardStop=True, unknownUsageBehavior="block",
            unknownPriceBehavior="block", allowZeroPrice=False,
        ),
    )
    return (
        ref("QuotaPolicyRevision", quota.policy_id, quota.content_hash),
        ref("BudgetPolicyRevision", budget_policy.policy_id, budget_policy.content_hash),
    )


def publish_network_policy(egress_ref: VersionedAssetRef) -> VersionedAssetRef:
    instant = datetime.now(UTC)
    network = AipNetworkPolicyStore().publish(
        SCOPE, SUFFIX, "network-policy-1",
        NetworkPolicyRevisionCreate(
            policyId=f"{SUFFIX}:network", revision=1,
            allowedSchemes=["https"], allowedHosts=["apihub.agnes-ai.com"],
            allowedPorts=[443], tlsRequired=True, publicFallbackAllowed=False,
            egressPolicyRef=egress_ref, effectiveFrom=instant - timedelta(minutes=30),
            effectiveUntil=instant + timedelta(days=20), owner=SUFFIX,
            approvalRef="approval:test:aip7-store", lifecycle="active",
        ),
    )
    return ref("NetworkPolicyRevision", network.policy_id, network.content_hash)


class _AllowGovernance:
    def require_model_dependencies(self, *_args) -> None:
        return None


class _RejectEvalGate:
    def require_exact_passed(self, *_args, **_kwargs) -> None:
        raise AipEvalGateDependencyBlocked("eval gate target drifted")


def test_active_model_publication_requires_exact_target_eval_gate() -> None:
    item = hashed(
        RegisteredModelRevision,
        dict(
            tenant=TENANT,
            registeredModelId=f"{SUFFIX}:active-model",
            revision=1,
            provider=ref("ProviderInstanceRevision", "provider", "1" * 64),
            providerModelId="model-test",
            inputModalities=[ModelModality.TEXT],
            outputModalities=[ModelModality.TEXT],
            capabilities=["structured_output"],
            contextWindow=4096,
            quotaPolicyRef=ref("QuotaPolicyRevision", "quota", "2" * 64),
            budgetPolicyRef=ref("BudgetPolicyRevision", "budget", "3" * 64),
            priceSnapshotRef=ref("ModelPriceSnapshotRevision", "price", "4" * 64),
            evalGateRef=ref("EvalGateDecision", "gate", "5" * 64),
            lifecycle=ModelRuntimeLifecycle.ACTIVE,
            createdBy=SUFFIX,
            createdAt=NOW,
        ),
    )
    store = AipModelRuntimeStore(
        governance_policy_store=_AllowGovernance(),
        eval_authority_store=_RejectEvalGate(),
    )
    with pytest.raises(ModelRuntimeDependencyBlocked, match="target drifted"):
        store.publish_model(SCOPE, SUFFIX, "active-model", item)


def test_store_persists_exact_chain_replays_receipt_and_isolates_tenant() -> None:
    cleanup()
    store = AipModelRuntimeStore()
    try:
        provider_without_guards = hashed(ProviderInstanceRevision, dict(
            tenant=TENANT, providerInstanceId=SUFFIX, revision=1,
            pluginRef=ref("ProviderPluginRevision", "test:plugin", "1" * 64),
            endpointProfile=ProviderEndpointProfile(baseUrl="https://provider.invalid/v1", region="cn", timeoutMs=10_000),
            secretRef="vault://aos/org-org/test-provider", secretVersion="1",
            egressPolicyRef=ref("EgressPolicyRevision", "test:egress", "2" * 64),
            dataClassificationPolicyRef=ref("DataClassificationPolicyRevision", "test:classification", "3" * 64),
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy=SUFFIX, createdAt=NOW,
        ))
        with pytest.raises(ModelRuntimeDependencyBlocked, match="exact runtime guard policy"):
            store.publish_provider(SCOPE, SUFFIX, "provider-missing-guards", provider_without_guards)

        egress_ref, data_classification_ref = publish_runtime_guards()
        provider_outside_egress = rehashed(
            provider_without_guards,
            egressPolicyRef=egress_ref.model_dump(mode="json", by_alias=True),
            dataClassificationPolicyRef=data_classification_ref.model_dump(mode="json", by_alias=True),
        )
        with pytest.raises(ModelRuntimeDependencyBlocked, match="outside exact egress policy"):
            store.publish_provider(SCOPE, SUFFIX, "provider-outside-egress", provider_outside_egress)

        provider = rehashed(
            provider_outside_egress,
            endpointProfile=ProviderEndpointProfile(
                baseUrl="https://apihub.agnes-ai.com/v1",
                region="cn-approved-development",
                timeoutMs=10_000,
            ).model_dump(mode="json", by_alias=True),
        )
        stored_provider = store.publish_provider(SCOPE, SUFFIX, "provider-1", provider)
        assert store.publish_provider(SCOPE, SUFFIX, "provider-1", provider) == stored_provider
        with pytest.raises(ModelRuntimeIdempotencyConflict):
            store.publish_provider(SCOPE, SUFFIX, "provider-1", rehashed(provider, secretVersion="2"))

        health = ProviderHealthObservation(
            tenant=TENANT, observationId=f"{SUFFIX}:health",
            provider=ref("ProviderInstanceRevision", SUFFIX, provider.content_hash),
            status="healthy", availabilityPct=100, p50LatencyMs=20,
            observedAt=NOW, expiresAt=NOW + timedelta(minutes=5),
        )
        assert store.record_health(SCOPE, SUFFIX, "health-1", health).status == "healthy"

        price = hashed(ModelPriceSnapshotRevision, dict(
            tenant=TENANT, priceSnapshotId=f"{SUFFIX}:price", revision=1,
            currency="CNY", inputTokenPrice=0.001, outputTokenPrice=0.002,
            tokenUnit=1000, effectiveFrom=NOW,
            lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy=SUFFIX, createdAt=NOW,
        ))
        store.publish_price_snapshot(SCOPE, SUFFIX, "price-1", price)

        model = hashed(RegisteredModelRevision, dict(
            tenant=TENANT, registeredModelId=f"{SUFFIX}:model", revision=1,
            provider=ref("ProviderInstanceRevision", SUFFIX, provider.content_hash), providerModelId="model-test",
            inputModalities=[ModelModality.TEXT], outputModalities=[ModelModality.TEXT],
            capabilities=["structured_output"], contextWindow=4096,
            quotaPolicyRef=ref("QuotaPolicyRevision", "test:quota", "4" * 64),
            budgetPolicyRef=ref("BudgetPolicyRevision", "test:budget", "5" * 64),
            priceSnapshotRef=ref("ModelPriceSnapshotRevision", price.price_snapshot_id, price.content_hash),
            evalGateRef=ref("EvalGateDecision", "test:eval", "7" * 64),
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy=SUFFIX, createdAt=NOW,
        ))
        with pytest.raises(ModelRuntimeDependencyBlocked, match="model governance policy"):
            store.publish_model(SCOPE, SUFFIX, "model-missing-governance", model)
        quota_ref, budget_policy_ref = publish_model_governance_policies()
        model = rehashed(
            model,
            quotaPolicyRef=quota_ref.model_dump(mode="json", by_alias=True),
            budgetPolicyRef=budget_policy_ref.model_dump(mode="json", by_alias=True),
        )
        store.publish_model(SCOPE, SUFFIX, "model-1", model)

        policy = hashed(RuntimePolicyRevision, dict(
            tenant=TENANT, policyId=f"{SUFFIX}:policy", revision=1,
            networkPolicyRef=ref("NetworkPolicyRevision", "test:network", "8" * 64),
            egressPolicyRef=egress_ref,
            dataClassificationPolicyRef=data_classification_ref,
            quotaPolicyRef=quota_ref,
            budgetPolicyRef=budget_policy_ref,
            deadlineMs=30_000, maxAttempts=2, allowedFallbackReasons=["provider_unavailable"],
            unknownUsageBehavior="block", unknownPriceBehavior="block", killSwitchEnabled=True,
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy=SUFFIX, createdAt=NOW,
        ))
        with pytest.raises(ModelRuntimeDependencyBlocked, match="network policy"):
            store.publish_policy(SCOPE, SUFFIX, "policy-missing-network", policy)
        network_ref = publish_network_policy(egress_ref)
        policy = rehashed(
            policy,
            networkPolicyRef=network_ref.model_dump(mode="json", by_alias=True),
        )
        store.publish_policy(SCOPE, SUFFIX, "policy-1", policy)

        route = hashed(ModelRouteRevision, dict(
            tenant=TENANT, routeId=f"{SUFFIX}:route", revision=1,
            taskTypes=["copy.generate"], requiredInputModality=ModelModality.TEXT,
            requiredOutputModality=ModelModality.TEXT, requiredCapabilities=["structured_output"],
            candidates=[ModelRouteCandidate(model=ref("RegisteredModelRevision", model.registered_model_id, model.content_hash))],
            strategy=RouteStrategy.FAILOVER,
            runtimePolicyRef=ref("RuntimePolicyRevision", policy.policy_id, policy.content_hash),
            evalGateRef=ref("EvalGateDecision", "test:eval", "7" * 64),
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy=SUFFIX, createdAt=NOW,
        ))
        assert store.publish_route(SCOPE, SUFFIX, "route-1", route).route_id == route.route_id
        with pytest.raises(ModelRuntimeNotFound):
            store.get_route(CANARY, route.route_id)
    finally:
        cleanup()
