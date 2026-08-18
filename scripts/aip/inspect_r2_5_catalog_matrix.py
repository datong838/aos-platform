#!/usr/bin/env python3
"""Read-only R2-5 catalog / combination matrix for DEP-ADP(query) evidence.

Default inspect never starts an AgentRun and never calls the business Provider.
--refresh-readiness re-evaluates existing active Bindings against current Health.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    EvaluateOperationalBindingRequest,
)
from aos_api.auth import Principal as AuthPrincipal
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-5-catalog-matrix"
CAPABILITY_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"
SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r4"
V8_RUN_ID = "ecommerce.data_advisor.D03.real-pilot.v8"
V8_ATTEMPT_ID = "ecommerce.data_advisor.D03.real-pilot.v8.attempt-1"
EVIDENCE = Path(__file__).resolve().parents[2] / ".evidence/aip/2026-08-18-r2-5-dep-adp-query-evidence.json"


class MatrixBlocked(RuntimeError):
    def __init__(self, code: str, reasons: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reasons = sorted(set(reasons or []))


def _principal() -> AuthPrincipal:
    return AuthPrincipal(subject=ACTOR, org_id=SCOPE.org_id, project_id=SCOPE.project_id, roles=["owner"])


def _health(now: datetime) -> dict[str, Any]:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT observation_id,status,observed_at,expires_at,p50_latency_ms "
            "FROM aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s ORDER BY observed_at DESC LIMIT 1",
            SCOPE.key,
        ).fetchone()
        canary = conn.execute(
            "SELECT COUNT(*) AS n FROM aip_agent_run WHERE org_id=%s AND project_id=%s",
            CANARY.key,
        ).fetchone()["n"]
        run = conn.execute(
            "SELECT status FROM aip_agent_run WHERE org_id=%s AND project_id=%s AND agent_run_id=%s",
            (*SCOPE.key, V8_RUN_ID),
        ).fetchone()
        attempt = conn.execute(
            "SELECT status,reason_code FROM aip_agent_run_execution_attempt "
            "WHERE org_id=%s AND project_id=%s AND attempt_id=%s",
            (*SCOPE.key, V8_ATTEMPT_ID),
        ).fetchone()
    if row is None or row["status"] != "healthy" or row["expires_at"] <= now:
        raise MatrixBlocked("PROVIDER_HEALTH_REFRESH_REQUIRED")
    return {
        "observationId": row["observation_id"],
        "p50LatencyMs": row["p50_latency_ms"],
        "expiresAt": row["expires_at"],
        "valid": True,
        "v8AgentRunStatus": None if run is None else run["status"],
        "v8AttemptStatus": None if attempt is None else attempt["status"],
        "canaryAgentRuns": int(canary),
    }


def refresh_readiness(*, now: datetime) -> dict[str, str]:
    facts = _health(now)
    health_key = str(facts["observationId"])
    capability_service = AipCapabilityBindingService()
    skill_service = AipSkillRegistry()
    capability = capability_service.get(SCOPE, CAPABILITY_BINDING_ID)
    binding = skill_service.get_binding(SCOPE, SKILL_BINDING_ID)
    if not (
        capability.status == "active"
        and capability.operational_readiness is CapabilityReadiness.AVAILABLE
        and capability.readiness_expires_at is not None
        and capability.readiness_expires_at > now
    ):
        capability, readiness, _ = capability_service.evaluate(
            SCOPE,
            CAPABILITY_BINDING_ID,
            EvaluateOperationalBindingRequest(
                expectedVersion=capability.version,
                dependencies=capability.dependencies,
            ),
            idempotency_key=f"r2-5-capability-readiness:{health_key}",
            actor=ACTOR,
            evaluated_at=now,
        )
        if (
            capability.status != "active"
            or readiness.readiness is not CapabilityReadiness.AVAILABLE
        ):
            raise MatrixBlocked("CAPABILITY_BINDING_NOT_READY", readiness.reasons)
    if not (
        binding.status == "active"
        and binding.readiness is CapabilityReadiness.AVAILABLE
        and binding.readiness_expires_at is not None
        and binding.readiness_expires_at > now
    ):
        binding, readiness, _ = skill_service.evaluate_binding(
            SCOPE,
            SKILL_BINDING_ID,
            EvaluateOperationalBindingRequest(
                expectedVersion=binding.version,
                dependencies=binding.dependencies,
            ),
            idempotency_key=f"r2-5-skill-readiness:{health_key}",
            actor=ACTOR,
            evaluated_at=now,
        )
        if binding.status != "active" or readiness.readiness is not CapabilityReadiness.AVAILABLE:
            raise MatrixBlocked("SKILL_BINDING_NOT_READY", readiness.reasons)
    return {
        "healthObservationId": health_key,
        "capabilityBindingId": capability.binding_id,
        "skillBindingId": binding.binding_id,
    }


def inspect(*, refresh: bool = False) -> dict[str, Any]:
    now = datetime.now(UTC)
    health = _health(now)
    refreshed = refresh_readiness(now=now) if refresh else {"skipped": True}
    catalog = AipEcommerceAgentInstaller().catalog(_principal())
    items = []
    for item in catalog.items:
        items.append(
            {
                "templateId": item.template.template_id,
                "displayName": item.template.display_name,
                "instanceStatus": None if item.instance is None else item.instance.status.value,
                "runtimeReadiness": item.runtime_readiness,
                "blockers": item.blockers,
                "publishedSkillCount": sum(
                    1 for skill in item.skills if skill.lifecycle.value == "published"
                ),
            }
        )
    data_advisor = next(row for row in items if row["templateId"] == "ecommerce.data_advisor")
    dep_adp = (
        "GREEN"
        if (
            catalog.stats.runnable_count == 1
            and data_advisor["runtimeReadiness"] == "runnable"
            and health["v8AgentRunStatus"] == "succeeded"
            and health["v8AttemptStatus"] == "succeeded"
            and health["canaryAgentRuns"] == 0
        )
        else "RED"
    )
    return {
        "status": "R2_5_DEP_ADP_QUERY_EVIDENCE_GREEN" if dep_adp == "GREEN" else "blocked",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "health": {
            "observationId": health["observationId"],
            "p50LatencyMs": health["p50LatencyMs"],
            "expiresAt": str(health["expiresAt"]),
        },
        "readinessRefresh": refreshed,
        "catalogStats": catalog.stats.model_dump(by_alias=True),
        "colleagues": items,
        "combination": {
            "skill": "ecommerce.skill.D03 r4",
            "capability": "strategy.plan r2",
            "route": "route-qyh-text-dev r4",
            "provider": "agnes-text-qyh-dev r7",
            "host": "api.agnes-ai.cn",
            "model": "agnes-2.5-flash",
            "agentRun": V8_RUN_ID,
            "attempt": V8_ATTEMPT_ID,
            "agentRunStatus": health["v8AgentRunStatus"],
            "attemptStatus": health["v8AttemptStatus"],
        },
        "depAdpQuery": {
            "dataAdvisorD03Text": dep_adp,
            "otherColleagues": "RED",
            "workshopPage": "unchanged_red_until_w2_consumes",
        },
        "canaryAgentRuns": health["canaryAgentRuns"],
        "providerBusinessCalls": 0,
        "secretPayloadReads": 0,
        "sensitiveBodiesPrinted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-readiness", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()
    try:
        result = inspect(refresh=args.refresh_readiness)
    except MatrixBlocked as exc:
        result = {
            "status": "blocked",
            "blockerCode": exc.code,
            "blockerReasons": exc.reasons,
            "providerBusinessCalls": 0,
        }
    if args.write_evidence and result.get("status") == "R2_5_DEP_ADP_QUERY_EVIDENCE_GREEN":
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "aos-aip-operational-evidence/v1",
            "wave": "R2-5",
            "recordedAt": datetime.now(UTC).astimezone().isoformat(),
            **result,
        }
        EVIDENCE.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
        result["evidencePath"] = str(EVIDENCE)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("status") == "R2_5_DEP_ADP_QUERY_EVIDENCE_GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
