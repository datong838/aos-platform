#!/usr/bin/env python3
"""Restricted R1 runtime authority bootstrap for org-org/dev-project.

Dry-run is the default.  The apply path publishes only the approved R1
prerequisites and promotes the already validated Provider revision; it never
creates a Binding or AgentRun and never prints a secret payload.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevisionCreate,
    QuotaPolicyRevisionCreate,
)
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_model_runtime_contracts import (
    ModelPriceSnapshotRevision,
    ModelRuntimeLifecycle,
    ProviderInstanceRevision,
    RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-r1-runtime-bootstrap"
APPROVAL_REF = "35-R1-C"
WINDOW_START = datetime(2026, 8, 17, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
WINDOW_END = datetime(2026, 10, 15, 23, 59, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}


def exact_ref(kind: str, item: Any) -> VersionedAssetRef:
    id_field = {
        "BudgetRevision": "budget_id",
        "QuotaPolicyRevision": "policy_id",
        "BudgetPolicyRevision": "policy_id",
        "NetworkPolicyRevision": "policy_id",
        "ProviderInstanceRevision": "provider_instance_id",
        "RuntimePolicyRevision": "policy_id",
        "ModelPriceSnapshotRevision": "price_snapshot_id",
    }[kind]
    return VersionedAssetRef(
        assetType=kind,
        assetId=getattr(item, id_field),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def rehash_runtime(model: type, payload: dict[str, Any]):
    provisional = model.model_validate({**payload, "contentHash": "0" * 64})
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {name: value for name, value in dumped.items() if name not in META_FIELDS}
    return model.model_validate({**payload, "contentHash": canonical_hash(content)})


def build_plan() -> dict[str, Any]:
    return {
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "approvalRef": APPROVAL_REF,
        "mode": "restricted-development",
        "steps": [
            "BudgetRevision",
            "QuotaPolicyRevision",
            "BudgetPolicyRevision",
            "ModelPriceSnapshotRevision",
            "NetworkPolicyRevision",
            "RuntimePolicyRevision",
            "ProviderInstanceRevision@2(active)",
        ],
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentRun"],
    }


def apply_prerequisites() -> dict[str, Any]:
    created_at = WINDOW_START.astimezone(UTC)
    runtime_store = AipModelRuntimeStore()
    governance_store = AipModelGovernancePolicyStore()
    provider_v1 = runtime_store.get_provider(SCOPE, "agnes-text-qyh-dev", 1)

    budget = AipBudgetAuthorityStore().publish(
        SCOPE,
        ACTOR,
        "r1-08-budget-qyh-text-dev-v1",
        BudgetRevisionCreate(
            budgetId="budget-qyh-text-dev",
            revision=1,
            dailyLimitMinor=500,
            monthlyLimitMinor=5000,
            alertThresholdPct=80,
            hardStop=True,
            unknownUsageBehavior="block",
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            overBudgetApprover="杜大同",
            lifecycle="active",
        ),
    )
    quota = governance_store.publish_quota(
        SCOPE,
        ACTOR,
        "r1-07-quota-qyh-text-dev-v1",
        QuotaPolicyRevisionCreate(
            policyId="quota-qyh-text-dev",
            revision=1,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            approvalRef=APPROVAL_REF,
            lifecycle="active",
            maxConcurrency=2,
            maxInputTokens=8000,
            maxOutputTokens=2000,
            hourlyRequestLimit=50,
            dailyRequestLimit=200,
            reservationLeaseSeconds=60,
            overflowBehavior="reject",
            allowPublicProviderFallback=False,
            allowAutoScale=False,
        ),
    )
    budget_policy = governance_store.publish_budget(
        SCOPE,
        ACTOR,
        "r1-08-budget-policy-qyh-text-dev-v1",
        BudgetPolicyRevisionCreate(
            policyId="budget-policy-qyh-text-dev",
            revision=1,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            approvalRef=APPROVAL_REF,
            lifecycle="active",
            budgetRevisionRef=exact_ref("BudgetRevision", budget),
            hardStop=True,
            unknownUsageBehavior="block",
            unknownPriceBehavior="block",
            allowZeroPrice=True,
            zeroPriceApprovalRef=APPROVAL_REF,
        ),
    )
    price = rehash_runtime(
        ModelPriceSnapshotRevision,
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "priceSnapshotId": "price-qyh-text-dev",
            "revision": 1,
            "currency": "CNY",
            "inputTokenPrice": 0,
            "outputTokenPrice": 0,
            "cachedTokenPrice": 0,
            "tokenUnit": 1000,
            "effectiveFrom": WINDOW_START,
            "effectiveUntil": WINDOW_END,
            "lifecycle": "active",
            "createdBy": ACTOR,
            "createdAt": created_at,
        },
    )
    price = runtime_store.publish_price_snapshot(
        SCOPE, ACTOR, "r1-08-price-qyh-text-dev-v1", price
    )
    network = AipNetworkPolicyStore().publish(
        SCOPE,
        ACTOR,
        "r1-04-network-qyh-text-dev-v1",
        NetworkPolicyRevisionCreate(
            policyId="network-qyh-text-dev",
            revision=1,
            allowedSchemes=["https"],
            allowedHosts=["apihub.agnes-ai.com"],
            allowedPorts=[443],
            tlsRequired=True,
            publicFallbackAllowed=False,
            egressPolicyRef=provider_v1.egress_policy_ref,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            approvalRef=APPROVAL_REF,
            lifecycle="active",
        ),
    )
    policy = rehash_runtime(
        RuntimePolicyRevision,
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "policyId": "policy-qyh-text-dev",
            "revision": 1,
            "networkPolicyRef": exact_ref("NetworkPolicyRevision", network),
            "egressPolicyRef": provider_v1.egress_policy_ref,
            "dataClassificationPolicyRef": provider_v1.data_classification_policy_ref,
            "quotaPolicyRef": exact_ref("QuotaPolicyRevision", quota),
            "budgetPolicyRef": exact_ref("BudgetPolicyRevision", budget_policy),
            "deadlineMs": 60000,
            "maxAttempts": 1,
            "allowedFallbackReasons": [],
            "unknownUsageBehavior": "block",
            "unknownPriceBehavior": "block",
            "killSwitchEnabled": False,
            "lifecycle": "active",
            "createdBy": ACTOR,
            "createdAt": created_at,
        },
    )
    policy = runtime_store.publish_policy(
        SCOPE, ACTOR, "r1-04-policy-qyh-text-dev-v1", policy
    )
    provider_payload = provider_v1.model_dump(mode="json", by_alias=True)
    provider_payload.update(
        revision=2,
        lifecycle=ModelRuntimeLifecycle.ACTIVE.value,
        createdBy=ACTOR,
        createdAt=created_at,
    )
    provider_payload.pop("contentHash", None)
    provider_v2 = rehash_runtime(ProviderInstanceRevision, provider_payload)
    provider_v2 = runtime_store.publish_provider(
        SCOPE,
        ACTOR,
        "r1-02-provider-agnes-text-qyh-dev-v2-active",
        provider_v2,
        expected_version=1,
    )
    assets = [budget, quota, budget_policy, price, network, policy, provider_v2]
    return {
        "status": "prerequisites-published",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "assets": [
            {
                "type": type(item).__name__,
                "id": next(
                    getattr(item, field)
                    for field in (
                        "budget_id",
                        "policy_id",
                        "price_snapshot_id",
                        "provider_instance_id",
                    )
                    if hasattr(item, field)
                ),
                "revision": item.revision,
                "contentHash": item.content_hash,
            }
            for item in assets
        ],
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentRun"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-prerequisites", action="store_true")
    args = parser.parse_args()
    result = apply_prerequisites() if args.apply_prerequisites else build_plan()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
