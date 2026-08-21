#!/usr/bin/env python3
"""Safely compose the six reviewed R06-R11 runtime-tail refreshers.

This command never probes a Provider.  It only consumes a separately-approved,
fresh 3/3 ProviderHealthObservation through the existing fail-closed binding
evaluators.  Default execution is a read-only plan; writes require ``--apply``.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

ROLE_REFRESHERS = (
    ("data_advisor", "refresh_r06_data_advisor_runtime_tail", "R06_DATA_ADVISOR_RUNTIME_TAIL_GREEN"),
    ("private_domain_manager", "refresh_r07_private_domain_manager_runtime_tail", "R07_PRIVATE_DOMAIN_RUNTIME_TAIL_GREEN"),
    ("shopping_advisor", "refresh_r08_shopping_advisor_runtime_tail", "R08_SHOPPING_ADVISOR_RUNTIME_TAIL_GREEN"),
    ("customer_service", "refresh_r09_customer_service_runtime_tail", "R09_CUSTOMER_SERVICE_RUNTIME_TAIL_GREEN"),
    ("campaign_planner", "refresh_r10_campaign_planner_runtime_tail", "R10_CAMPAIGN_PLANNER_RUNTIME_TAIL_GREEN"),
    ("content_officer", "refresh_r11_content_officer_runtime_tail", "R11_CONTENT_OFFICER_RUNTIME_TAIL_GREEN"),
)
D03_SKILL_ID = "ecommerce.skill.D03"
D03_SKILL_REVISION = 4
D03_BINDING_ID = "ecommerce.data_advisor.skill.D03.r4"
D03_CAPABILITY_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"


class R12RuntimeRefreshBlocked(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        completed_roles: list[str] | None = None,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.completed_roles = completed_roles or []
        self.details = details or []


def _load_refreshers() -> list[tuple[str, str, Callable[..., dict[str, Any]]]]:
    result = []
    for role, module_name, expected_status in ROLE_REFRESHERS:
        module = importlib.import_module(module_name)
        result.append((role, expected_status, module.apply))
    return result


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": "org-org", "projectId": "dev-project"},
        "roles": [role for role, _, _ in ROLE_REFRESHERS],
        "precondition": "fresh separately-approved 3/3 text ProviderHealthObservation",
        "semantics": "compose reviewed R06-R11 runtime-tail refreshers; no republish",
        "preservedImmutablePilot": {
            "logicId": "D03",
            "bindingId": D03_BINDING_ID,
            "operation": "readiness metadata refresh only; never replay AgentRun",
        },
        "providerCalls": 0,
        "agentRuns": 0,
        "externalActions": 0,
        "secretPayloadReads": 0,
    }


def _refresh_immutable_d03(*, now: datetime) -> dict[str, Any]:
    """Refresh only the exact D03 SkillBinding readiness metadata.

    D03's published Graph/Eval/Skill and successful historical AgentRun are
    immutable.  This function re-evaluates the existing r4 binding against its
    exact stored dependencies after the shared strategy capability has been
    refreshed; it never imports or invokes the pilot executor.
    """
    from aos_api.aip_agent_registry_contracts import (
        CapabilityReadiness,
        EvaluateOperationalBindingRequest,
        VersionedAssetRef,
    )
    from aos_api.aip_skill_registry import AipSkillRegistry
    from aos_api.db import connect as db_connect
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope("org-org", "dev-project")
    canary_scope = TenantScope("dev-org", "dev-project")

    def canary_count() -> int:
        with db_connect(canary_scope) as conn:
            return int(
                conn.execute(
                    """SELECT COUNT(*) AS n FROM aip_skill_binding
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                    (*canary_scope.key, D03_BINDING_ID),
                ).fetchone()["n"]
            )

    if canary_count() != 0:
        raise RuntimeError("D03_NEGATIVE_CANARY_NOT_EMPTY")
    registry = AipSkillRegistry()
    skill = registry.get_skill(D03_SKILL_ID, D03_SKILL_REVISION)
    binding = registry.get_binding(scope, D03_BINDING_ID)
    expected_skill = VersionedAssetRef(
        assetType="SkillTemplate",
        assetId=skill.skill_id,
        revision=skill.revision,
        contentHash=skill.content_hash,
    )
    if binding.status != "active" or binding.skill != expected_skill:
        raise RuntimeError("D03_EXACT_ACTIVE_BINDING_REQUIRED")
    if binding.capability_binding_ids != [D03_CAPABILITY_BINDING_ID]:
        raise RuntimeError("D03_CAPABILITY_BINDING_DRIFT")
    dependencies = binding.dependencies
    if (
        dependencies.model_route_ref != skill.model_route_ref
        or dependencies.runtime_policy_ref != skill.runtime_policy_ref
        or dependencies.eval_gate_ref != skill.release_gate_ref
    ):
        raise RuntimeError("D03_EXACT_DEPENDENCY_DRIFT")
    binding, readiness, _ = registry.evaluate_binding(
        scope,
        D03_BINDING_ID,
        EvaluateOperationalBindingRequest(
            expectedVersion=binding.version,
            dependencies=dependencies,
        ),
        idempotency_key=f"r12-d03-readiness-{int(now.timestamp())}",
        actor="aip-r12-runtime-readiness-refresh",
        evaluated_at=now,
    )
    if readiness.readiness is not CapabilityReadiness.AVAILABLE:
        raise RuntimeError(
            "D03_READINESS_BLOCKED:" + ",".join(readiness.reasons)
        )
    if canary_count() != 0:
        raise RuntimeError("D03_NEGATIVE_CANARY_CHANGED")
    return {
        "status": "R12_D03_READINESS_METADATA_GREEN",
        "bindingId": binding.binding_id,
        "bindingVersion": binding.version,
        "readiness": readiness.readiness.value,
        "readinessExpiresAt": readiness.expires_at,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "secretPayloadReads": 0,
    }


def apply(
    *,
    now: datetime | None = None,
    refreshers: Iterable[tuple[str, str, Callable[..., dict[str, Any]]]] | None = None,
    d03_refresh: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evaluated_at = now or datetime.now(UTC)
    completed: list[str] = []
    results: list[dict[str, Any]] = []
    selected_refreshers = _load_refreshers() if refreshers is None else list(refreshers)
    for role, expected_status, refresh in selected_refreshers:
        try:
            result = refresh(now=evaluated_at)
        except Exception as exc:
            raise R12RuntimeRefreshBlocked(
                "ROLE_RUNTIME_REFRESH_FAILED",
                completed_roles=completed,
                details=[role, type(exc).__name__, str(exc)],
            ) from exc
        if result.get("status") != expected_status:
            raise R12RuntimeRefreshBlocked(
                "ROLE_RUNTIME_REFRESH_STATUS_DRIFT",
                completed_roles=completed,
                details=[role, str(result.get("status")), expected_status],
            )
        for key in ("providerCalls", "agentRunsCreated", "secretPayloadReads"):
            if int(result.get(key) or 0) != 0:
                raise R12RuntimeRefreshBlocked(
                    "FORBIDDEN_SIDE_EFFECT_REPORTED",
                    completed_roles=completed,
                    details=[role, key, str(result.get(key))],
                )
        completed.append(role)
        results.append(
            {
                "role": role,
                "status": result["status"],
                "activeSkillBindingCount": result.get("activeSkillBindingCount"),
                "capabilityBindingCount": len(result.get("capabilityBindings") or []),
                "negativeCanaryCounts": result.get("negativeCanaryCounts"),
            }
        )
    try:
        d03_result = (d03_refresh or _refresh_immutable_d03)(now=evaluated_at)
    except Exception as exc:
        raise R12RuntimeRefreshBlocked(
            "D03_READINESS_METADATA_REFRESH_FAILED",
            completed_roles=completed,
            details=[type(exc).__name__, str(exc)],
        ) from exc
    if d03_result.get("status") != "R12_D03_READINESS_METADATA_GREEN":
        raise R12RuntimeRefreshBlocked(
            "D03_READINESS_METADATA_STATUS_DRIFT",
            completed_roles=completed,
            details=[str(d03_result.get("status"))],
        )
    for key in ("providerCalls", "agentRunsCreated", "secretPayloadReads"):
        if int(d03_result.get(key) or 0) != 0:
            raise R12RuntimeRefreshBlocked(
                "FORBIDDEN_SIDE_EFFECT_REPORTED",
                completed_roles=completed,
                details=["D03", key, str(d03_result.get(key))],
            )
    return {
        "status": "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN",
        "scope": {"orgId": "org-org", "projectId": "dev-project"},
        "evaluatedAt": evaluated_at,
        "completedRoles": completed,
        "roleResults": results,
        "immutableD03": d03_result,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "externalActions": 0,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else build_plan()
        exit_code = 0
    except R12RuntimeRefreshBlocked as exc:
        result = {
            **build_plan(),
            "status": "blocked",
            "blockerCode": exc.code,
            "completedRoles": exc.completed_roles,
            "blockerDetails": exc.details,
        }
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
