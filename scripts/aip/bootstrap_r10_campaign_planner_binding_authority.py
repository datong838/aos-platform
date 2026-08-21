#!/usr/bin/env python3
"""Compose five missing R10 campaign-planner SkillBindings without AgentRun.

The command is fail-closed. It binds only exact published Skill revisions,
preserves the existing A02 binding and active campaign-planner instance, and
never calls a Provider or performs a campaign-visible action. Expired capability readiness
keeps a binding in ``provisioning`` with explicit reasons.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest,
    OperationalBindingDependencies,
    UpdateSkillBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r10-campaign-planner-binding-bootstrap"
REQUIRED_ALEMBIC_HEAD = "aip13_001"
INSTANCE_ID = "ecommerce.campaign_planner.default"
POLICY_ID = "policy-qyh-text-dev"
POLICY_REVISION = 2
A02_BINDING_ID = "ecommerce.campaign_planner.skill.A02.r2"

BINDING_SPECS = {
    "A01": [
        "ecommerce.shared.material.collect.r1",
        "ecommerce.shared.performance.review.r1",
    ],
    "A03": [
        "ecommerce.data_advisor.strategy.plan.r2",
        "ecommerce.shared.performance.review.r1",
    ],
    "A04": ["ecommerce.data_advisor.strategy.plan.r2"],
    "A05": ["ecommerce.shared.performance.review.r1"],
    "A06": ["ecommerce.shared.performance.review.r1"],
}

_EXPECTED_RUNTIME_TAIL = {
    "CAPABILITY_BINDING_NOT_ACTIVE",
    "CAPABILITY_HEALTH_STALE",
}


class BindingCompositionBlocked(RuntimeError):
    def __init__(self, code: str, reasons: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reasons = sorted(set(reasons or []))


def exact_ref(asset_type: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=str(getattr(item, id_attr)),
        revision=int(item.revision),
        content_hash=str(item.content_hash),
    )


def binding_id(logic_id: str) -> str:
    return f"ecommerce.campaign_planner.skill.{logic_id}.r2"


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "instanceId": INSTANCE_ID,
        "preservedAuthority": [A02_BINDING_ID],
        "bindings": [
            {
                "logicId": logic_id,
                "bindingId": binding_id(logic_id),
                "skill": f"ecommerce.skill.{logic_id}@r2",
                "capabilityBindingIds": capability_ids,
            }
            for logic_id, capability_ids in BINDING_SPECS.items()
        ],
        "providerCalls": 0,
        "agentRuns": 0,
        "externalCampaignActions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def _require_schema_head() -> None:
    with db_connect(SCOPE) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    current = str(row["version_num"]) if row else ""
    if current != REQUIRED_ALEMBIC_HEAD:
        raise BindingCompositionBlocked(
            "SCHEMA_HEAD_MISMATCH",
            [f"expected={REQUIRED_ALEMBIC_HEAD}", f"actual={current}"],
        )


def _counts(scope: TenantScope) -> dict[str, int]:
    ids = [binding_id(logic_id) for logic_id in BINDING_SPECS]
    with db_connect(scope) as conn:
        skill_bindings = int(
            conn.execute(
                """SELECT COUNT(*) AS n FROM aip_skill_binding
                   WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""",
                (*scope.key, ids),
            ).fetchone()["n"]
        )
        agent_runs = int(
            conn.execute(
                """SELECT COUNT(*) AS n FROM aip_agent_run
                   WHERE org_id=%s AND project_id=%s""",
                scope.key,
            ).fetchone()["n"]
        )
    return {"skillBindings": skill_bindings, "agentRuns": agent_runs}


def _snapshot_a02(registry: AipSkillRegistry) -> dict[str, Any]:
    item = registry.get_binding(SCOPE, A02_BINDING_ID)
    return item.model_dump(mode="json", by_alias=True)


def _dependencies(
    skill: Any, budget_policy_ref: VersionedAssetRef
) -> OperationalBindingDependencies:
    if (
        skill.release_gate_ref is None
        or skill.model_route_ref is None
        or skill.runtime_policy_ref is None
        or skill.logic_revision_ref is None
    ):
        raise BindingCompositionBlocked(
            "SKILL_PUBLICATION_PROVENANCE_MISSING", [skill.skill_id]
        )
    return OperationalBindingDependencies(
        model_route_ref=skill.model_route_ref,
        runtime_policy_ref=skill.runtime_policy_ref,
        eval_gate_ref=skill.release_gate_ref,
        budget_policy_ref=budget_policy_ref,
        allow_degraded=False,
    )


def _ensure_binding(
    registry: AipSkillRegistry,
    *,
    logic_id: str,
    budget_policy_ref: VersionedAssetRef,
    evaluated_at: datetime,
) -> Any:
    skill = registry.get_skill(f"ecommerce.skill.{logic_id}", 2)
    skill_ref = exact_ref("SkillTemplate", skill, "skill_id")
    target_binding_id = binding_id(logic_id)
    try:
        binding = registry.get_binding(SCOPE, target_binding_id)
        if binding.skill != skill_ref:
            raise BindingCompositionBlocked(
                "SKILL_BINDING_EXACT_REF_DRIFT", [target_binding_id]
            )
        if binding.capability_binding_ids != BINDING_SPECS[logic_id]:
            raise BindingCompositionBlocked(
                "SKILL_BINDING_CAPABILITY_DRIFT", [target_binding_id]
            )
    except Exception as exc:
        from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound

        if not isinstance(exc, AipAgentRegistryNotFound):
            raise
        binding, _ = registry.create_binding(
            SCOPE,
            CreateSkillBindingRequest(
                binding_id=target_binding_id,
                instance_id=INSTANCE_ID,
                skill=skill_ref,
                capability_binding_ids=BINDING_SPECS[logic_id],
                budget_policy_ref=budget_policy_ref,
            ),
            idempotency_key=f"R10-{logic_id}-skill-binding-create-r2",
            actor=ACTOR,
            occurred_at=evaluated_at,
        )

    dependencies = _dependencies(skill, budget_policy_ref)
    binding, readiness, _ = registry.evaluate_binding(
        SCOPE,
        target_binding_id,
        EvaluateOperationalBindingRequest(
            expected_version=binding.version,
            dependencies=dependencies,
        ),
        idempotency_key=(
            f"R10-{logic_id}-skill-binding-evaluate-r2-v{binding.version}"
        ),
        actor=ACTOR,
        evaluated_at=evaluated_at,
    )
    if readiness.readiness is CapabilityReadiness.AVAILABLE:
        if binding.status == "provisioning":
            binding, _ = registry.update_binding(
                SCOPE,
                target_binding_id,
                UpdateSkillBindingRequest(
                    expected_version=binding.version,
                    from_status="provisioning",
                    to_status="active",
                ),
                idempotency_key=(
                    f"R10-{logic_id}-skill-binding-activate-r2-v{binding.version}"
                ),
                actor=ACTOR,
                occurred_at=evaluated_at,
            )
        elif binding.status != "active":
            raise BindingCompositionBlocked(
                "SKILL_BINDING_LIFECYCLE_NOT_ACTIVATABLE",
                [target_binding_id, binding.status],
            )
    elif not set(readiness.reasons).issubset(_EXPECTED_RUNTIME_TAIL):
        raise BindingCompositionBlocked(
            "UNEXPECTED_SKILL_BINDING_BLOCKER",
            [target_binding_id, *readiness.reasons],
        )
    return registry.get_binding(SCOPE, target_binding_id)


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    _require_schema_head()
    evaluated_at = now or datetime.now(UTC)
    canary_before = _counts(CANARY_SCOPE)
    if canary_before["skillBindings"]:
        raise BindingCompositionBlocked("NEGATIVE_CANARY_NOT_EMPTY")

    instance = AipAgentRegistryStore().get_instance(SCOPE, INSTANCE_ID)
    if instance.status.value != "active":
        raise BindingCompositionBlocked("CAMPAIGN_PLANNER_INSTANCE_NOT_ACTIVE")
    policy = AipModelRuntimeStore().get_policy(SCOPE, POLICY_ID, POLICY_REVISION)
    registry = AipSkillRegistry()
    a02_before = _snapshot_a02(registry)
    results = [
        _ensure_binding(
            registry,
            logic_id=logic_id,
            budget_policy_ref=policy.budget_policy_ref,
            evaluated_at=evaluated_at,
        )
        for logic_id in BINDING_SPECS
    ]

    a02_after = _snapshot_a02(registry)
    if a02_after != a02_before:
        raise BindingCompositionBlocked("IMMUTABLE_A02_BINDING_CHANGED")
    canary_after = _counts(CANARY_SCOPE)
    if canary_after != canary_before:
        raise BindingCompositionBlocked("NEGATIVE_CANARY_CHANGED")
    runtime_tail = sorted(
        {reason for item in results for reason in item.readiness_reasons}
    )
    active_count = sum(item.status == "active" for item in results)
    return {
        "status": (
            "R10_CAMPAIGN_PLANNER_BINDING_GREEN"
            if active_count == len(results)
            else "R10_CAMPAIGN_PLANNER_BINDING_GREEN_WITH_RUNTIME_TAIL"
        ),
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "instance": {"instanceId": INSTANCE_ID, "status": instance.status.value},
        "bindings": [
            {
                "bindingId": item.binding_id,
                "skill": item.skill.model_dump(mode="json", by_alias=True),
                "status": item.status,
                "readiness": item.readiness.value,
                "readinessReasons": item.readiness_reasons,
                "capabilityBindingIds": item.capability_binding_ids,
            }
            for item in results
        ],
        "activeCount": active_count,
        "runtimeTail": runtime_tail,
        "preservedA02": a02_after,
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "externalCampaignActions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else build_plan()
    except BindingCompositionBlocked as exc:
        result = {
            **build_plan(),
            "status": "blocked",
            "blockerCode": exc.code,
            "blockerReasons": exc.reasons,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
