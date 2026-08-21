#!/usr/bin/env python3
"""Refresh exact capability snapshots and resume all six R09 bindings.

This command does not call a Provider. It may run only after a separately
approved 3/3 text Provider Health refresh. It re-evaluates four active exact
CapabilityBindings, activates the five new SkillBindings, and refreshes the
operational snapshot of the pre-existing S04 SkillBinding without changing its
Skill/Logic/Capability composition.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    EvaluateOperationalBindingRequest,
)
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap_r09_customer_service_binding_authority as binding_authority  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r09-customer-service-runtime-tail-refresh"
CAPABILITY_BINDING_IDS = (
    "ecommerce.data_advisor.strategy.plan.r2",
    "ecommerce.shared.copy.generate.r1",
    "ecommerce.shared.material.collect.r1",
    "ecommerce.shared.performance.review.r1",
)
S04_BINDING_ID = binding_authority.S04_BINDING_ID


class RuntimeTailBlocked(RuntimeError):
    def __init__(self, code: str, reasons: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reasons = sorted(set(reasons or []))


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "capabilityBindings": list(CAPABILITY_BINDING_IDS),
        "skillBindings": [
            binding_authority.binding_id(logic_id)
            for logic_id in binding_authority.BINDING_SPECS
        ]
        + [S04_BINDING_ID],
        "precondition": "fresh separately-approved 3/3 ProviderHealthObservation",
        "providerCalls": 0,
        "agentRuns": 0,
        "externalCustomerActions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def _canary_counts() -> dict[str, int]:
    with db_connect(CANARY_SCOPE) as conn:
        capabilities = int(
            conn.execute(
                """SELECT COUNT(*) AS n FROM aip_capability_binding
                   WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""",
                (*CANARY_SCOPE.key, list(CAPABILITY_BINDING_IDS)),
            ).fetchone()["n"]
        )
        s04 = int(
            conn.execute(
                """SELECT COUNT(*) AS n FROM aip_skill_binding
                   WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                (*CANARY_SCOPE.key, S04_BINDING_ID),
            ).fetchone()["n"]
        )
    return {
        "capabilityBindings": capabilities,
        "s04SkillBinding": s04,
        **binding_authority._counts(CANARY_SCOPE),
    }


def _refresh_s04(registry: AipSkillRegistry, evaluated_at: datetime) -> Any:
    before = registry.get_binding(SCOPE, S04_BINDING_ID)
    exact_composition = {
        "skill": before.skill,
        "capabilityBindingIds": list(before.capability_binding_ids),
        "budgetPolicyRef": before.budget_policy_ref,
    }
    after, readiness, _ = registry.evaluate_binding(
        SCOPE,
        S04_BINDING_ID,
        EvaluateOperationalBindingRequest(
            expected_version=before.version,
            dependencies=before.dependencies,
        ),
        idempotency_key=f"R09-runtime-tail-S04-v{before.version}",
        actor=ACTOR,
        evaluated_at=evaluated_at,
    )
    if readiness.readiness is not CapabilityReadiness.AVAILABLE:
        raise RuntimeTailBlocked(
            "S04_SKILL_BINDING_REEVALUATION_BLOCKED", list(readiness.reasons)
        )
    if after.status != "active":
        raise RuntimeTailBlocked("S04_SKILL_BINDING_NOT_ACTIVE", [after.status])
    if {
        "skill": after.skill,
        "capabilityBindingIds": list(after.capability_binding_ids),
        "budgetPolicyRef": after.budget_policy_ref,
    } != exact_composition:
        raise RuntimeTailBlocked("S04_EXACT_COMPOSITION_CHANGED")
    return after


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    evaluated_at = now or datetime.now(UTC)
    canary_before = _canary_counts()
    if any(
        canary_before[key]
        for key in ("capabilityBindings", "skillBindings", "s04SkillBinding")
    ):
        raise RuntimeTailBlocked("NEGATIVE_CANARY_NOT_EMPTY")

    service = AipCapabilityBindingService()
    capabilities = []
    for binding_id in CAPABILITY_BINDING_IDS:
        current = service.get(SCOPE, binding_id)
        if current.status != "active":
            raise RuntimeTailBlocked(
                "CAPABILITY_BINDING_NOT_ACTIVE", [binding_id, current.status]
            )
        current, readiness, _ = service.evaluate(
            SCOPE,
            binding_id,
            EvaluateOperationalBindingRequest(
                expected_version=current.version,
                dependencies=current.dependencies,
            ),
            idempotency_key=f"R09-runtime-tail-{binding_id}-v{current.version}",
            actor=ACTOR,
            evaluated_at=evaluated_at,
        )
        if readiness.readiness is not CapabilityReadiness.AVAILABLE:
            raise RuntimeTailBlocked(
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
    if skill_result["status"] != "R09_CUSTOMER_SERVICE_BINDING_GREEN":
        raise RuntimeTailBlocked(
            "SKILL_BINDING_RUNTIME_TAIL_REMAINS",
            list(skill_result.get("runtimeTail") or []),
        )
    s04 = _refresh_s04(AipSkillRegistry(), evaluated_at)
    canary_after = _canary_counts()
    if canary_after != canary_before:
        raise RuntimeTailBlocked("NEGATIVE_CANARY_CHANGED")
    return {
        "status": "R09_CUSTOMER_SERVICE_RUNTIME_TAIL_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "capabilityBindings": capabilities,
        "skillBindings": skill_result["bindings"]
        + [
            {
                "bindingId": s04.binding_id,
                "skill": s04.skill.model_dump(mode="json", by_alias=True),
                "status": s04.status,
                "readiness": s04.readiness.value,
                "readinessReasons": s04.readiness_reasons,
                "capabilityBindingIds": s04.capability_binding_ids,
            }
        ],
        "activeSkillBindingCount": skill_result["activeCount"] + 1,
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "externalCustomerActions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else build_plan()
    except RuntimeTailBlocked as exc:
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

