#!/usr/bin/env python3
"""Refresh exact capability snapshots and resume R06 SkillBindings.

This command does not call a Provider.  It may only be executed after a
separately approved 3/3 Provider health refresh has written a fresh authority
observation.  It re-evaluates the two already-active capability bindings from
their stored exact dependency sets, then resumes the five R06 SkillBindings.
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
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap_r06_data_advisor_binding_authority as binding_authority  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r06-data-advisor-runtime-tail-refresh"
CAPABILITY_BINDING_IDS = (
    "ecommerce.shared.material.collect.r1",
    "ecommerce.shared.performance.review.r1",
)


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
        ],
        "precondition": "fresh separately-approved 3/3 ProviderHealthObservation",
        "providerCalls": 0,
        "agentRuns": 0,
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
    return {
        "capabilityBindings": capabilities,
        **binding_authority._counts(CANARY_SCOPE),
    }


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    evaluated_at = now or datetime.now(UTC)
    canary_before = _canary_counts()
    if canary_before["capabilityBindings"] or canary_before["skillBindings"]:
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
            idempotency_key=(
                f"R06-runtime-tail-{binding_id}-v{current.version}"
            ),
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
    if skill_result["status"] != "R06_DATA_ADVISOR_BINDING_GREEN":
        raise RuntimeTailBlocked(
            "SKILL_BINDING_RUNTIME_TAIL_REMAINS",
            list(skill_result.get("runtimeTail") or []),
        )
    canary_after = _canary_counts()
    if canary_after != canary_before:
        raise RuntimeTailBlocked("NEGATIVE_CANARY_CHANGED")
    return {
        "status": "R06_DATA_ADVISOR_RUNTIME_TAIL_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "capabilityBindings": capabilities,
        "skillBindings": skill_result["bindings"],
        "activeSkillBindingCount": skill_result["activeCount"],
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "agentRunsCreated": 0,
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
