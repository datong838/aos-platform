from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    ModelRuntimeIdempotencyConflict,
    ModelRuntimeNotFound,
    canonical_hash,
)
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
CANARY = TenantScope(org_id="dev-org", project_id="dev-project")
TENANT = TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id)
NOW = datetime.now(UTC)
SUFFIX = "test:aip7-store"


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


def test_store_persists_exact_chain_replays_receipt_and_isolates_tenant() -> None:
    cleanup()
    store = AipModelRuntimeStore()
    try:
        provider = hashed(ProviderInstanceRevision, dict(
            tenant=TENANT, providerInstanceId=SUFFIX, revision=1,
            pluginRef=ref("ProviderPluginRevision", "test:plugin", "1" * 64),
            endpointProfile=ProviderEndpointProfile(baseUrl="https://provider.invalid/v1", region="cn", timeoutMs=10_000),
            secretRef="vault://aos/org-org/test-provider", secretVersion="1",
            egressPolicyRef=ref("EgressPolicyRevision", "test:egress", "2" * 64),
            dataClassificationPolicyRef=ref("DataClassificationPolicyRevision", "test:classification", "3" * 64),
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy=SUFFIX, createdAt=NOW,
        ))
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
        store.publish_model(SCOPE, SUFFIX, "model-1", model)

        policy = hashed(RuntimePolicyRevision, dict(
            tenant=TENANT, policyId=f"{SUFFIX}:policy", revision=1,
            networkPolicyRef=ref("NetworkPolicyRevision", "test:network", "8" * 64),
            egressPolicyRef=ref("EgressPolicyRevision", "test:egress", "2" * 64),
            dataClassificationPolicyRef=ref("DataClassificationPolicyRevision", "test:classification", "3" * 64),
            quotaPolicyRef=ref("QuotaPolicyRevision", "test:quota", "4" * 64),
            budgetPolicyRef=ref("BudgetPolicyRevision", "test:budget", "5" * 64),
            deadlineMs=30_000, maxAttempts=2, allowedFallbackReasons=["provider_unavailable"],
            unknownUsageBehavior="block", unknownPriceBehavior="block", killSwitchEnabled=True,
            lifecycle=ModelRuntimeLifecycle.VALIDATED, createdBy=SUFFIX, createdAt=NOW,
        ))
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
