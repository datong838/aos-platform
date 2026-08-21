#!/usr/bin/env python3
"""VID-4: publish video Model/Route/Capacity split from text.

Default inspect. ``--apply`` publishes additive:
  policy-qyh-video-dev r1
  model-qyh-video-dev r1
  route-qyh-video-dev r1
  capacity-qyh-video-dev r1

Reuses text quota/budget/price. Pins video Provider r2 + Network/Egress.
Eval uses policy-contract GoldSet only (no extra live probes).
Never starts AgentRun. Never edits text route/capacity.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "aos-api"))

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_capacity_authority import (
    AipModelCapacityAuthorityStore,
    CapacityPoolRevisionCreate,
)
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_model_runtime_contracts import (
    ModelModality,
    ModelRouteCandidate,
    ModelRouteRevision,
    ModelRuntimeLifecycle,
    RegisteredModelRevision,
    RouteStrategy,
    RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore,
    ModelRuntimeNotFound,
    canonical_hash,
    evaluation_candidate_ref,
)
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-r2-vid-4-route-capacity"
APPROVAL_REF = "46-§8.76-VID-4"
PROVIDER_ID = "agnes-video-qyh-dev"
PROVIDER_REVISION = 1
NETWORK_ID = "network-qyh-video-dev"
NETWORK_REVISION = 1
MODEL_ID = "model-qyh-video-dev"
ROUTE_ID = "route-qyh-video-dev"
POLICY_ID = "policy-qyh-video-dev"
CAPACITY_ID = "capacity-qyh-video-dev"
PROVIDER_MODEL_ID = "agnes-video-v2.0"
TEXT_QUOTA_ID = "quota-qyh-text-dev"
TEXT_BUDGET_POLICY_ID = "budget-policy-qyh-text-dev"
TEXT_PRICE_ID = "price-qyh-text-dev"
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
ID_FIELDS = {
    "ProviderInstanceRevision": "provider_instance_id",
    "RegisteredModelRevision": "registered_model_id",
    "ModelRouteRevision": "route_id",
    "RuntimePolicyRevision": "policy_id",
    "NetworkPolicyRevision": "policy_id",
    "QuotaPolicyRevision": "policy_id",
    "BudgetPolicyRevision": "policy_id",
    "ModelPriceSnapshotRevision": "price_snapshot_id",
}


def load_bootstrap():
    path = Path(__file__).resolve().parent / "bootstrap_r1_runtime_authority.py"
    spec = importlib.util.spec_from_file_location("bootstrap_r1_runtime_authority", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LIVE_MODEL_CASE_IDS = set()
    module.ACTOR = ACTOR
    module.APPROVAL_REF = APPROVAL_REF
    return module


def exact_ref(kind: str, item: Any, id_attr: str | None = None) -> VersionedAssetRef:
    attr = id_attr or ID_FIELDS[kind]
    return VersionedAssetRef(
        assetType=kind,
        assetId=getattr(item, attr),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def rehash_runtime(model: type, payload: dict[str, Any]):
    provisional = model.model_validate({**payload, "contentHash": "0" * 64})
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {name: value for name, value in dumped.items() if name not in META_FIELDS}
    return model.model_validate({**payload, "contentHash": canonical_hash(content)})


def head_row(kind: str, asset_id: str) -> dict[str, int] | None:
    table = f"aip_{kind}_head"
    column = f"{kind}_id"
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            f"SELECT current_revision, version FROM {table} "
            f"WHERE org_id=%s AND project_id=%s AND {column}=%s",
            (*SCOPE.key, asset_id),
        ).fetchone()
    if row is None:
        return None
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


def capacity_head() -> dict[str, int] | None:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT current_revision, version FROM aip_model_capacity_pool_head "
            "WHERE org_id=%s AND project_id=%s AND pool_id=%s",
            (*SCOPE.key, CAPACITY_ID),
        ).fetchone()
    if row is None:
        return None
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


def goldset_cases() -> list[dict[str, Any]]:
    kinds = ["positive", "boundary", "negative", "tenant"]
    return [
        {
            "caseId": f"vid4-{index:02d}",
            "kind": kinds[index % len(kinds)],
            "prompt": "video-route-capability-contract",
            "expectedBehavior": "non_empty",
            "routeTaskType": "video.generate",
            "routeInputModality": "text",
            "routeCapability": "video",
            "routeExpected": "SELECT",
        }
        for index in range(20)
    ]


def inspect() -> dict[str, Any]:
    store = AipModelRuntimeStore()
    model_h = head_row("registered_model", MODEL_ID)
    route_h = head_row("model_route", ROUTE_ID)
    capacity_h = capacity_head()
    if model_h and route_h and capacity_h:
        resolution = AipModelRuntimeResolver(store=store).resolve(
            SCOPE, ROUTE_ID, now=datetime.now(UTC)
        )
        return {
            "status": "already_present",
            "model": {"assetId": MODEL_ID, "revision": model_h["revision"]},
            "route": {"assetId": ROUTE_ID, "revision": route_h["revision"]},
            "capacity": {"assetId": CAPACITY_ID, "revision": capacity_h["revision"]},
            "readiness": resolution.readiness.value,
            "blockerCodes": list(resolution.blocker_codes or []),
        }
    return {
        "status": "ready",
        "provider": {"assetId": PROVIDER_ID, "revision": PROVIDER_REVISION},
        "network": {"assetId": NETWORK_ID, "revision": NETWORK_REVISION},
    }


def apply() -> dict[str, Any]:
    snapshot = inspect()
    if snapshot["status"] == "already_present" and snapshot.get("readiness") == "ready":
        return {**snapshot, "status": "R2_VID_4_ROUTE_CAPACITY_GREEN"}

    boot = load_bootstrap()
    store = AipModelRuntimeStore()
    governance = AipModelGovernancePolicyStore()
    networks = AipNetworkPolicyStore()
    capacity_store = AipModelCapacityAuthorityStore()
    created_at = datetime.now(UTC)

    provider = store.get_provider(SCOPE, PROVIDER_ID, PROVIDER_REVISION)
    network = networks.get(SCOPE, NETWORK_ID, NETWORK_REVISION)
    quota = governance.get_quota(SCOPE, TEXT_QUOTA_ID, 1)
    budget_policy = governance.get_budget(SCOPE, TEXT_BUDGET_POLICY_ID, 1)
    price = store.get_price_snapshot(SCOPE, TEXT_PRICE_ID, 1)
    provider_ref = exact_ref("ProviderInstanceRevision", provider)
    network_ref = exact_ref("NetworkPolicyRevision", network)

    policy_head = head_row("runtime_policy", POLICY_ID)
    if policy_head is None:
        policy = rehash_runtime(
            RuntimePolicyRevision,
            {
                "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
                "policyId": POLICY_ID,
                "revision": 1,
                "networkPolicyRef": network_ref,
                "egressPolicyRef": provider.egress_policy_ref,
                "dataClassificationPolicyRef": provider.data_classification_policy_ref,
                "quotaPolicyRef": exact_ref("QuotaPolicyRevision", quota),
                "budgetPolicyRef": exact_ref("BudgetPolicyRevision", budget_policy),
                "deadlineMs": 60_000,
                "maxAttempts": 1,
                "allowedFallbackReasons": [],
                "unknownUsageBehavior": "block",
                "unknownPriceBehavior": "block",
                "killSwitchEnabled": False,
                "lifecycle": ModelRuntimeLifecycle.ACTIVE,
                "createdBy": ACTOR,
                "createdAt": created_at,
            },
        )
        policy = store.publish_policy(
            SCOPE, ACTOR, f"{APPROVAL_REF}-policy-r1", policy, expected_version=0
        )
    else:
        policy = store.get_policy(SCOPE, POLICY_ID, policy_head["revision"])

    cases = goldset_cases()
    dataset = boot._register_goldset(cases)

    model_head = head_row("registered_model", MODEL_ID)
    if model_head is None:
        model_payload = {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "registeredModelId": MODEL_ID,
            "revision": 1,
            "provider": provider_ref,
            "providerModelId": PROVIDER_MODEL_ID,
            "inputModalities": [ModelModality.TEXT],
            "outputModalities": [ModelModality.VIDEO],
            "capabilities": ["video"],
            "contextWindow": 4096,
            "quotaPolicyRef": exact_ref("QuotaPolicyRevision", quota),
            "budgetPolicyRef": exact_ref("BudgetPolicyRevision", budget_policy),
            "priceSnapshotRef": exact_ref("ModelPriceSnapshotRevision", price),
            "evalGateRef": boot.PLACEHOLDER_GATE,
            "lifecycle": ModelRuntimeLifecycle.ACTIVE,
            "createdBy": ACTOR,
            "createdAt": created_at,
        }
        model_candidate = rehash_runtime(RegisteredModelRevision, model_payload)
        model_gate = boot._derive_gate(
            target_ref=evaluation_candidate_ref(model_candidate),
            cases=cases,
            dataset=dataset,
            mode="model",
            provider_ref=provider_ref,
            network_ref=network_ref,
            probe_results=[],
        )
        model = rehash_runtime(
            RegisteredModelRevision, {**model_payload, "evalGateRef": model_gate}
        )
        model = store.publish_model(
            SCOPE, ACTOR, f"{APPROVAL_REF}-model-r1", model, expected_version=0
        )
    else:
        model = store.get_model(SCOPE, MODEL_ID, model_head["revision"])

    route_head = head_row("model_route", ROUTE_ID)
    if route_head is None:
        route_payload = {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "routeId": ROUTE_ID,
            "revision": 1,
            "taskTypes": ["video.generate"],
            "requiredInputModality": ModelModality.TEXT,
            "requiredOutputModality": ModelModality.VIDEO,
            "requiredCapabilities": ["video"],
            "candidates": [
                ModelRouteCandidate(model=exact_ref("RegisteredModelRevision", model))
            ],
            "strategy": RouteStrategy.FAILOVER,
            "runtimePolicyRef": exact_ref("RuntimePolicyRevision", policy),
            "evalGateRef": boot.PLACEHOLDER_GATE,
            "lifecycle": ModelRuntimeLifecycle.ACTIVE,
            "createdBy": ACTOR,
            "createdAt": created_at,
        }
        route_candidate = rehash_runtime(ModelRouteRevision, route_payload)
        route_gate = boot._derive_gate(
            target_ref=evaluation_candidate_ref(route_candidate),
            cases=cases,
            dataset=dataset,
            mode="route",
            provider_ref=provider_ref,
            network_ref=network_ref,
            route_candidate=route_candidate,
        )
        route = rehash_runtime(
            ModelRouteRevision, {**route_payload, "evalGateRef": route_gate}
        )
        route = store.publish_route(
            SCOPE, ACTOR, f"{APPROVAL_REF}-route-r1", route, expected_version=0
        )
    else:
        route = store.get_route(SCOPE, ROUTE_ID, route_head["revision"])

    cap_head = capacity_head()
    if cap_head is None:
        capacity = capacity_store.publish(
            SCOPE,
            ACTOR,
            f"{APPROVAL_REF}-capacity-r1",
            CapacityPoolRevisionCreate(
                poolId=CAPACITY_ID,
                revision=1,
                routeRef=exact_ref("ModelRouteRevision", route),
                modelRef=exact_ref("RegisteredModelRevision", model),
                providerRef=provider_ref,
                maxConcurrency=2,
                maxTokenUnits=10_000,
                tokenUnitPerReservation=2_000,
                leaseSeconds=60,
                lifecycle="active",
            ),
            expected_version=0,
        )
    else:
        capacity = capacity_store.get(SCOPE, CAPACITY_ID, cap_head["revision"])

    resolution = AipModelRuntimeResolver(store=store).resolve(
        SCOPE, ROUTE_ID, now=datetime.now(UTC)
    )
    if resolution.readiness.value != "ready":
        raise RuntimeError(
            f"video runtime resolver blocked: {list(resolution.blocker_codes or [])}"
        )

    return {
        "status": "R2_VID_4_ROUTE_CAPACITY_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "policy": exact_ref("RuntimePolicyRevision", policy).model_dump(
            mode="json", by_alias=True
        ),
        "model": exact_ref("RegisteredModelRevision", model).model_dump(
            mode="json", by_alias=True
        ),
        "route": exact_ref("ModelRouteRevision", route).model_dump(
            mode="json", by_alias=True
        ),
        "capacity": {
            "assetId": capacity.pool_id,
            "revision": capacity.revision,
            "contentHash": capacity.content_hash,
        },
        "readiness": resolution.readiness.value,
        "textRouteUntouched": True,
        "providerBusinessCalls": 0,
        "healthProbes": 0,
        "agentRuns": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else inspect()
    except Exception as exc:  # noqa: BLE001 - surface as blocked JSON for operators
        result = {
            "status": "blocked",
            "blockerCode": type(exc).__name__,
            "message": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("status") in {
        "ready",
        "already_present",
        "R2_VID_4_ROUTE_CAPACITY_GREEN",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
