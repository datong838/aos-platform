#!/usr/bin/env python3
"""Materialize A0-V fail-closed runtime configuration authority in isolation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
RECOVERY_ROOT = ROOT.parent / ".aos-recovery-20260910"
API_ROOT = ROOT / "services/aos-api"
FIRST_INSTALLER = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
ACTOR = "a0v-current-runtime-configuration-authority"
APPROVAL_REF = "approval:AOS-000573:A0-V-local-readonly"
WINDOW_START = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2027, 9, 10, 0, 0, tzinfo=UTC)
IDS = {
    "egress": "a0v-ecommerce-egress-v1",
    "data": "a0v-ecommerce-public-catalog-v1",
    "network": "a0v-ecommerce-network-v1",
    "budget": "a0v-ecommerce-hard-stop-budget-v1",
    "quota": "a0v-ecommerce-quota-v1",
    "budgetPolicy": "a0v-ecommerce-budget-policy-v1",
    "runtimePolicy": "a0v-ecommerce-runtime-policy-v1",
}


class ConfigurationAuthorityBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default="colima-aos-extension")
    parser.add_argument("--database-container", default="aos-a0v-recovery-pg")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=RECOVERY_ROOT / "state/a0v-current-runtime-configuration-authority",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _load_first_installer() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_first_install", FIRST_INSTALLER)
    if spec is None or spec.loader is None:
        raise ConfigurationAuthorityBlocked("FIRST_INSTALLER_UNAVAILABLE", str(FIRST_INSTALLER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _asset_ref(item: Any, resource_type: str, identity: str) -> Any:
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef

    return VersionedAssetRef(
        assetType=resource_type,
        assetId=getattr(item, identity),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def _inventory(connect: Any) -> dict[str, Any]:
    queries = {
        "egress": ("aip_runtime_guard_policy_head", "policy_kind='egress' AND policy_id=%s", IDS["egress"]),
        "data": ("aip_runtime_guard_policy_head", "policy_kind='data_classification' AND policy_id=%s", IDS["data"]),
        "network": ("aip_network_policy_head", "policy_id=%s", IDS["network"]),
        "budget": ("aip_budget_head", "budget_id=%s", IDS["budget"]),
        "quota": ("aip_model_governance_policy_head", "policy_kind='quota' AND policy_id=%s", IDS["quota"]),
        "budgetPolicy": ("aip_model_governance_policy_head", "policy_kind='budget' AND policy_id=%s", IDS["budgetPolicy"]),
        "runtimePolicy": ("aip_runtime_policy_head", "runtime_policy_id=%s", IDS["runtimePolicy"]),
    }
    with connect() as conn:
        identity = conn.execute("SELECT current_database() AS database").fetchone()
        if identity is None or identity["database"] != "aos_meta_head":
            raise ConfigurationAuthorityBlocked("DATABASE_IDENTITY_MISMATCH", str(identity))
        counts = {}
        for name, (table, condition, value) in queries.items():
            row = conn.execute(
                f"SELECT count(*) AS count FROM {table} WHERE org_id=%s AND project_id=%s AND {condition}",
                (ORG_ID, PROJECT_ID, value),
            ).fetchone()
            counts[name] = int(row["count"])
        canary = {}
        for name, (table, condition, value) in queries.items():
            row = conn.execute(
                f"SELECT count(*) AS count FROM {table} WHERE org_id=%s AND project_id=%s AND {condition}",
                (CANARY_ORG_ID, CANARY_PROJECT_ID, value),
            ).fetchone()
            canary[name] = int(row["count"])
        if any(canary.values()):
            raise ConfigurationAuthorityBlocked("CANARY_AUTHORITY_NOT_EMPTY", str(canary))
        role = conn.execute(
            """SELECT count(*) AS count FROM aip_responsibility_plan_head h
               JOIN aip_responsibility_plan_revision r
                 ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.plan_id=h.plan_id AND r.revision=h.current_revision
              WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='frozen'""",
            (ORG_ID, PROJECT_ID),
        ).fetchone()
        counts["frozenResponsibilityPlan"] = int(role["count"])
        return {"counts": counts, "canaryCounts": canary}


def _scoped_factory(connect: Any):
    def scoped(_scope=None):
        return connect()

    return scoped


def _publish_policy_chain(connect: Any) -> dict[str, Any]:
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_budget_contracts import BudgetRevisionCreate
    from aos_api.aip_budget_store import AipBudgetAuthorityStore
    from aos_api.aip_contracts import TenantContext
    from aos_api.aip_model_governance_policy_contracts import (
        BudgetPolicyRevisionCreate,
        QuotaPolicyRevisionCreate,
    )
    from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
    from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle, RuntimePolicyRevision
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash
    from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
    from aos_api.aip_network_policy_store import AipNetworkPolicyStore
    from aos_api.aip_runtime_guard_policy_contracts import (
        DataClassificationPolicyRevisionCreate,
        EgressPolicyRevisionCreate,
    )
    from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(ORG_ID, PROJECT_ID)
    factory = _scoped_factory(connect)
    guard = AipRuntimeGuardPolicyStore(factory)
    budget_store = AipBudgetAuthorityStore(factory)
    governance = AipModelGovernancePolicyStore(factory, budget_store=budget_store)
    network_store = AipNetworkPolicyStore(factory, guard_policy_store=guard)
    runtime_store = AipModelRuntimeStore(
        factory,
        guard_policy_store=guard,
        governance_policy_store=governance,
        network_policy_store=network_store,
    )
    common = dict(
        revision=1,
        environment="development",
        effectiveFrom=WINDOW_START,
        effectiveUntil=WINDOW_END,
        owner=ACTOR,
        approvalRef=APPROVAL_REF,
        lifecycle="active",
    )
    egress = guard.publish_egress(
        scope,
        ACTOR,
        "a0v-config-egress-v1",
        EgressPolicyRevisionCreate(
            policyId=IDS["egress"],
            allowedSchemes=["https"],
            allowedHosts=["api.agnes-ai.cn"],
            allowedPorts=[443],
            allowPublicFallback=False,
            unknownDestinationBehavior="block",
            regionState="confirmed",
            region="cn-approved-development",
            **common,
        ),
    )
    data = guard.publish_data_classification(
        scope,
        ACTOR,
        "a0v-config-data-v1",
        DataClassificationPolicyRevisionCreate(
            policyId=IDS["data"],
            allowedClassifications=["public_catalog"],
            prohibitedClassifications=[
                "direct_pii",
                "raw_order_detail",
                "customer_conversation",
                "credential",
                "commercial_sensitive",
                "cross_tenant",
                "unknown",
            ],
            denyUnknown=True,
            allowDirectPii=False,
            allowCommercialSensitive=False,
            allowCrossTenant=False,
            **common,
        ),
    )
    egress_ref = _asset_ref(egress, "EgressPolicyRevision", "policy_id")
    data_ref = _asset_ref(data, "DataClassificationPolicyRevision", "policy_id")
    network = network_store.publish(
        scope,
        ACTOR,
        "a0v-config-network-v1",
        NetworkPolicyRevisionCreate(
            policyId=IDS["network"],
            revision=1,
            allowedSchemes=["https"],
            allowedHosts=["api.agnes-ai.cn"],
            allowedPorts=[443],
            tlsRequired=True,
            publicFallbackAllowed=False,
            egressPolicyRef=egress_ref,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner=ACTOR,
            approvalRef=APPROVAL_REF,
            lifecycle="active",
        ),
    )
    budget = budget_store.publish(
        scope,
        ACTOR,
        "a0v-config-budget-v1",
        BudgetRevisionCreate(
            budgetId=IDS["budget"],
            revision=1,
            environment="development",
            currency="CNY",
            dailyLimitMinor=10000,
            monthlyLimitMinor=100000,
            alertThresholdPct=80,
            hardStop=True,
            unknownUsageBehavior="block",
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner=ACTOR,
            overBudgetApprover="a0v-local-human-checker",
            lifecycle="active",
        ),
    )
    quota = governance.publish_quota(
        scope,
        ACTOR,
        "a0v-config-quota-v1",
        QuotaPolicyRevisionCreate(
            policyId=IDS["quota"],
            revision=1,
            environment="development",
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner=ACTOR,
            approvalRef=APPROVAL_REF,
            lifecycle="active",
            maxConcurrency=1,
            maxInputTokens=8000,
            maxOutputTokens=2000,
            hourlyRequestLimit=10,
            dailyRequestLimit=50,
            reservationLeaseSeconds=60,
            overflowBehavior="queue",
            allowPublicProviderFallback=False,
            allowAutoScale=False,
        ),
    )
    budget_policy = governance.publish_budget(
        scope,
        ACTOR,
        "a0v-config-budget-policy-v1",
        BudgetPolicyRevisionCreate(
            policyId=IDS["budgetPolicy"],
            revision=1,
            environment="development",
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner=ACTOR,
            approvalRef=APPROVAL_REF,
            lifecycle="active",
            budgetRevisionRef=_asset_ref(budget, "BudgetRevision", "budget_id"),
            currency="CNY",
            hardStop=True,
            unknownUsageBehavior="block",
            unknownPriceBehavior="block",
            allowZeroPrice=False,
        ),
    )
    payload = dict(
        tenant=TenantContext(orgId=ORG_ID, projectId=PROJECT_ID),
        policyId=IDS["runtimePolicy"],
        revision=1,
        networkPolicyRef=_asset_ref(network, "NetworkPolicyRevision", "policy_id"),
        egressPolicyRef=egress_ref,
        dataClassificationPolicyRef=data_ref,
        quotaPolicyRef=_asset_ref(quota, "QuotaPolicyRevision", "policy_id"),
        budgetPolicyRef=_asset_ref(budget_policy, "BudgetPolicyRevision", "policy_id"),
        deadlineMs=10000,
        maxAttempts=1,
        allowedFallbackReasons=[],
        unknownUsageBehavior="block",
        unknownPriceBehavior="block",
        killSwitchEnabled=False,
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        createdBy=ACTOR,
        createdAt=WINDOW_START,
    )
    provisional = RuntimePolicyRevision(**payload, contentHash="0" * 64)
    content = {
        key: value
        for key, value in provisional.model_dump(mode="json", by_alias=True).items()
        if key not in AipModelRuntimeStore._META_FIELDS
    }
    runtime_policy = runtime_store.publish_policy(
        scope,
        ACTOR,
        "a0v-config-runtime-policy-v1",
        RuntimePolicyRevision(**payload, contentHash=canonical_hash(content)),
    )
    return {
        "egress": egress,
        "data": data,
        "network": network,
        "budget": budget,
        "quota": quota,
        "budgetPolicy": budget_policy,
        "runtimePolicy": runtime_policy,
    }


def _materialize_investigation_authority(connect: Any) -> dict[str, Any]:
    from aos_api.ecommerce_business_investigation_aip_authority import (
        BusinessInvestigationAuthorityMaterializer,
    )
    from aos_api.tenant_scope import TenantScope

    materializer = BusinessInvestigationAuthorityMaterializer(
        connect_factory=_scoped_factory(connect)
    )
    try:
        result = materializer.ensure(TenantScope(ORG_ID, PROJECT_ID), actor=ACTOR)
    except ValueError as exc:
        return {"ready": False, "blocker": str(exc)}
    plan = result.responsibility_plan
    return {
        "ready": plan.lifecycle.value == "frozen",
        "stageTemplateId": result.stage_template.template_id,
        "stageTemplateRevision": result.stage_template.revision,
        "stageTemplateLifecycle": result.stage_template.lifecycle.value,
        "responsibilityPlanId": plan.plan_id,
        "responsibilityPlanRevision": plan.revision,
        "responsibilityPlanHash": plan.content_hash,
        "responsibilityPlanLifecycle": plan.lifecycle.value,
        "responsibilityPlanReadiness": plan.readiness.value,
        "blockers": [item.code for item in plan.blockers],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.apply:
        return {
            "outcome": "PREFLIGHT_GREEN",
            "mode": "preflight",
            "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
            "authorityIds": IDS,
            "effects": {"providerInvocationCount": 0, "externalPublicationCount": 0},
        }
    if args.database_name != "aos_meta_head":
        raise ConfigurationAuthorityBlocked(
            "EXPLICIT_ISOLATED_DATABASE_REQUIRED", "aos_meta_head"
        )
    installer = _load_first_installer()
    connect = installer.container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    before = _inventory(connect)
    backup = installer.create_pre_mutation_backup(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
        state_dir=args.state_dir,
    )
    sys.path.insert(0, str(API_ROOT))
    try:
        policies = _publish_policy_chain(connect)
        investigation = _materialize_investigation_authority(connect)
    finally:
        sys.path.remove(str(API_ROOT))
    after = _inventory(connect)
    policy_receipt = {
        name: {
            "id": getattr(item, "policy_id", getattr(item, "budget_id", None)),
            "revision": item.revision,
            "contentHash": item.content_hash,
            "lifecycle": item.lifecycle.value,
        }
        for name, item in policies.items()
    }
    mutations = sum(
        max(0, after["counts"][name] - before["counts"][name]) for name in IDS
    )
    ready = investigation.get("ready") is True and after["counts"]["frozenResponsibilityPlan"] > 0
    return {
        "outcome": (
            "A0V_CURRENT_RUNTIME_CONFIGURATION_AUTHORITY_GREEN"
            if ready
            else "A0V_CURRENT_RUNTIME_CONFIGURATION_AUTHORITY_BLOCKED"
        ),
        "mode": "apply",
        "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
        "before": before,
        "backup": backup,
        "after": after,
        "policies": policy_receipt,
        "investigationAuthority": investigation,
        "mutationCount": mutations,
        "effects": {"providerInvocationCount": 0, "externalPublicationCount": 0},
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
    except ConfigurationAuthorityBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code, "message": str(exc)}
        status = 2
    else:
        status = 0
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
