#!/usr/bin/env python3
"""Refresh exact text capability snapshots and activate all R11 bindings."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap_r11_content_officer_binding_authority as binding_authority
import refresh_r10_campaign_planner_runtime_tail as _base

SCOPE = _base.SCOPE
CANARY_SCOPE = _base.CANARY_SCOPE
ACTOR = "aip-r11-content-officer-runtime-tail-refresh"
CAPABILITY_BINDING_IDS = (
    "ecommerce.data_advisor.strategy.plan.r2",
    "ecommerce.shared.material.collect.r1",
    "ecommerce.shared.copy.generate.r1",
    "ecommerce.shared.script.compose.r1",
    "ecommerce.shared.platform.adapt.r1",
    "ecommerce.shared.content.review.r1",
    "ecommerce.shared.performance.review.r1",
)
C02_BINDING_ID = binding_authority.C02_BINDING_ID


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "capabilityBindings": list(CAPABILITY_BINDING_IDS),
        "skillBindings": [
            binding_authority.binding_id(logic_id)
            for logic_id in binding_authority.BINDING_SPECS
        ]
        + [C02_BINDING_ID],
        "precondition": "fresh separately-approved 3/3 ProviderHealthObservation",
        "providerCalls": 0,
        "agentRuns": 0,
        "externalContentActions": 0,
        "mediaGenerations": 0,
        "memoryPromotions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def _canary_counts() -> dict[str, int]:
    with _base.db_connect(CANARY_SCOPE) as conn:
        capabilities = int(
            conn.execute(
                """SELECT COUNT(*) AS n FROM aip_capability_binding
                   WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""",
                (*CANARY_SCOPE.key, list(CAPABILITY_BINDING_IDS)),
            ).fetchone()["n"]
        )
        c02 = int(
            conn.execute(
                """SELECT COUNT(*) AS n FROM aip_skill_binding
                   WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                (*CANARY_SCOPE.key, C02_BINDING_ID),
            ).fetchone()["n"]
        )
    return {
        "capabilityBindings": capabilities,
        "c02SkillBinding": c02,
        **binding_authority._base._counts(CANARY_SCOPE),
    }


def _refresh_c02(registry: Any, evaluated_at: datetime) -> Any:
    before = registry.get_binding(SCOPE, C02_BINDING_ID)
    exact_composition = {
        "skill": before.skill,
        "capabilityBindingIds": list(before.capability_binding_ids),
        "budgetPolicyRef": before.budget_policy_ref,
    }
    after, readiness, _ = registry.evaluate_binding(
        SCOPE,
        C02_BINDING_ID,
        _base.EvaluateOperationalBindingRequest(
            expected_version=before.version,
            dependencies=before.dependencies,
        ),
        idempotency_key=f"R11-runtime-tail-C02-v{before.version}",
        actor=ACTOR,
        evaluated_at=evaluated_at,
    )
    if readiness.readiness is not _base.CapabilityReadiness.AVAILABLE:
        raise _base.RuntimeTailBlocked(
            "C02_SKILL_BINDING_REEVALUATION_BLOCKED", list(readiness.reasons)
        )
    if after.status != "active":
        raise _base.RuntimeTailBlocked("C02_SKILL_BINDING_NOT_ACTIVE", [after.status])
    if {
        "skill": after.skill,
        "capabilityBindingIds": list(after.capability_binding_ids),
        "budgetPolicyRef": after.budget_policy_ref,
    } != exact_composition:
        raise _base.RuntimeTailBlocked("C02_EXACT_COMPOSITION_CHANGED")
    return after


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    evaluated_at = now or datetime.now(UTC)
    canary_before = _canary_counts()
    if any(
        canary_before[key]
        for key in ("capabilityBindings", "skillBindings", "c02SkillBinding")
    ):
        raise _base.RuntimeTailBlocked("NEGATIVE_CANARY_NOT_EMPTY")

    service = _base.AipCapabilityBindingService()
    capabilities = []
    for binding_id in CAPABILITY_BINDING_IDS:
        current = service.get(SCOPE, binding_id)
        if current.status != "active":
            raise _base.RuntimeTailBlocked(
                "CAPABILITY_BINDING_NOT_ACTIVE", [binding_id, current.status]
            )
        current, readiness, _ = service.evaluate(
            SCOPE,
            binding_id,
            _base.EvaluateOperationalBindingRequest(
                expected_version=current.version,
                dependencies=current.dependencies,
            ),
            idempotency_key=f"R11-runtime-tail-{binding_id}-v{current.version}",
            actor=ACTOR,
            evaluated_at=evaluated_at,
        )
        if readiness.readiness is not _base.CapabilityReadiness.AVAILABLE:
            raise _base.RuntimeTailBlocked(
                "CAPABILITY_REEVALUATION_BLOCKED",
                [binding_id, *readiness.reasons],
            )
        capabilities.append(
            {
                "bindingId": current.binding_id,
                "status": current.status,
                "readiness": readiness.readiness.value,
                "readinessExpiresAt": readiness.expires_at,
            }
        )

    skill_result = binding_authority.apply(now=evaluated_at)
    if skill_result["status"] != "R11_CONTENT_OFFICER_BINDING_GREEN":
        raise _base.RuntimeTailBlocked(
            "SKILL_BINDING_RUNTIME_TAIL_REMAINS",
            list(skill_result.get("runtimeTail") or []),
        )
    c02 = _refresh_c02(_base.AipSkillRegistry(), evaluated_at)
    canary_after = _canary_counts()
    if canary_after != canary_before:
        raise _base.RuntimeTailBlocked("NEGATIVE_CANARY_CHANGED")
    return {
        "status": "R11_CONTENT_OFFICER_RUNTIME_TAIL_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "capabilityBindings": capabilities,
        "skillBindings": skill_result["bindings"]
        + [
            {
                "bindingId": c02.binding_id,
                "skill": c02.skill.model_dump(mode="json", by_alias=True),
                "status": c02.status,
                "readiness": c02.readiness.value,
                "readinessReasons": c02.readiness_reasons,
                "capabilityBindingIds": c02.capability_binding_ids,
            }
        ],
        "activeSkillBindingCount": skill_result["activeCount"] + 1,
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "externalContentActions": 0,
        "mediaGenerations": 0,
        "memoryPromotions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else build_plan()
    except _base.RuntimeTailBlocked as exc:
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
