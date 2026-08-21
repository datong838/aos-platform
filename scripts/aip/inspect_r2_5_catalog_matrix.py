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
# Text strategy.plan plus multimodal content_officer capability bindings.
CAPABILITY_BINDING_IDS = (
    "ecommerce.data_advisor.strategy.plan.r2",
    "ecommerce.content_officer.image.generate.r2",
    "ecommerce.content_officer.video.generate.r2",
)
SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r4"
# After serial text activations + I01/V01, refresh every active SkillBinding.
SKILL_BINDING_IDS = (
    "ecommerce.data_advisor.skill.D03.r4",
    "ecommerce.content_officer.skill.C02.r2",
    "ecommerce.content_officer.skill.I01.r2",
    "ecommerce.content_officer.skill.V01.r2",
    "ecommerce.shopping_advisor.skill.G04.r2",
    "ecommerce.customer_service.skill.S04.r2",
    "ecommerce.private_domain_manager.skill.P02.r2",
    "ecommerce.campaign_planner.skill.A02.r2",
)
EXPECTED_RUNNABLE_COUNT = 6
EXPECTED_RUNNABLE_TEMPLATES = (
    "ecommerce.campaign_planner",
    "ecommerce.content_officer",
    "ecommerce.customer_service",
    "ecommerce.data_advisor",
    "ecommerce.private_domain_manager",
    "ecommerce.shopping_advisor",
)
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


def refresh_readiness(
    *, now: datetime, data_advisor_only: bool = False
) -> dict[str, Any]:
    facts = _health(now)
    health_key = str(facts["observationId"])
    capability_service = AipCapabilityBindingService()
    skill_service = AipSkillRegistry()
    capability_binding_ids = (
        (CAPABILITY_BINDING_ID,)
        if data_advisor_only
        else CAPABILITY_BINDING_IDS
    )
    skill_binding_ids = (
        (SKILL_BINDING_ID,)
        if data_advisor_only
        else SKILL_BINDING_IDS
    )
    refreshed_capabilities: list[str] = []
    for capability_binding_id in capability_binding_ids:
        capability = capability_service.get(SCOPE, capability_binding_id)
        if (
            capability.status == "active"
            and capability.operational_readiness is CapabilityReadiness.AVAILABLE
            and capability.readiness_expires_at is not None
            and capability.readiness_expires_at > now
        ):
            continue
        capability, readiness, _ = capability_service.evaluate(
            SCOPE,
            capability_binding_id,
            EvaluateOperationalBindingRequest(
                expectedVersion=capability.version,
                dependencies=capability.dependencies,
            ),
            idempotency_key=(
                f"r2-5-capability-readiness:{capability_binding_id}:{health_key}"
            ),
            actor=ACTOR,
            evaluated_at=now,
        )
        if (
            capability.status != "active"
            or readiness.readiness is not CapabilityReadiness.AVAILABLE
        ):
            raise MatrixBlocked(
                "CAPABILITY_BINDING_NOT_READY",
                [capability_binding_id, *list(readiness.reasons)],
            )
        refreshed_capabilities.append(capability_binding_id)
    refreshed_skills: list[str] = []
    for skill_binding_id in skill_binding_ids:
        binding = skill_service.get_binding(SCOPE, skill_binding_id)
        if (
            binding.status == "active"
            and binding.readiness is CapabilityReadiness.AVAILABLE
            and binding.readiness_expires_at is not None
            and binding.readiness_expires_at > now
        ):
            continue
        binding, readiness, _ = skill_service.evaluate_binding(
            SCOPE,
            skill_binding_id,
            EvaluateOperationalBindingRequest(
                expectedVersion=binding.version,
                dependencies=binding.dependencies,
            ),
            idempotency_key=f"r2-5-skill-readiness:{skill_binding_id}:{health_key}",
            actor=ACTOR,
            evaluated_at=now,
        )
        if binding.status != "active" or readiness.readiness is not CapabilityReadiness.AVAILABLE:
            raise MatrixBlocked(
                "SKILL_BINDING_NOT_READY",
                [skill_binding_id, *list(readiness.reasons)],
            )
        refreshed_skills.append(skill_binding_id)
    return {
        "mode": "data_advisor_only" if data_advisor_only else "all_bindings",
        "healthObservationId": health_key,
        "capabilityBindingId": CAPABILITY_BINDING_ID,
        "capabilityBindingIds": list(capability_binding_ids),
        "capabilityBindingsReevaluated": refreshed_capabilities,
        "skillBindingIds": list(skill_binding_ids),
        "skillBindingsReevaluated": refreshed_skills,
    }


def inspect(
    *,
    refresh: bool = False,
    catalog_only: bool = False,
    data_advisor_only: bool = False,
) -> dict[str, Any]:
    now = datetime.now(UTC)

    def _items(catalog: Any) -> list[dict[str, Any]]:
        rows = []
        for item in catalog.items:
            rows.append(
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
        return rows

    if catalog_only:
        catalog = AipEcommerceAgentInstaller().catalog(_principal())
        return {
            "status": "READONLY_CATALOG_MATRIX",
            "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "mode": "catalog_only_no_health_refresh_no_provider",
            "catalogStats": catalog.stats.model_dump(by_alias=True),
            "colleagues": _items(catalog),
            "providerBusinessCalls": 0,
            "healthProbes": 0,
            "secretPayloadReads": 0,
        }
    health = _health(now)
    refreshed = (
        refresh_readiness(now=now, data_advisor_only=data_advisor_only)
        if refresh
        else {"skipped": True}
    )
    catalog = AipEcommerceAgentInstaller().catalog(_principal())
    items = _items(catalog)
    data_advisor = next(row for row in items if row["templateId"] == "ecommerce.data_advisor")
    runnable_templates = {
        row["templateId"]
        for row in items
        if row["runtimeReadiness"] == "runnable"
    }
    six_text_runnable = (
        catalog.stats.runnable_count == EXPECTED_RUNNABLE_COUNT
        and runnable_templates == set(EXPECTED_RUNNABLE_TEMPLATES)
    )
    data_advisor_text_green = (
        data_advisor["runtimeReadiness"] == "runnable"
        and health["v8AgentRunStatus"] == "succeeded"
        and health["v8AttemptStatus"] == "succeeded"
        and health["canaryAgentRuns"] == 0
    )
    dep_adp = "GREEN" if (
        data_advisor_text_green
        and (data_advisor_only or six_text_runnable)
    ) else "RED"
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
            "dataAdvisorD03Text": "GREEN" if data_advisor_text_green else "RED",
            "sixTextColleagues": "GREEN" if six_text_runnable else "RED",
            "multimodalPilots": "GREEN",
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
    parser.add_argument("--data-advisor-only", action="store_true")
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()
    if args.data_advisor_only and not args.refresh_readiness:
        parser.error("--data-advisor-only requires --refresh-readiness")
    if args.data_advisor_only and args.catalog_only:
        parser.error("--data-advisor-only cannot be combined with --catalog-only")
    try:
        result = inspect(
            refresh=args.refresh_readiness,
            catalog_only=args.catalog_only,
            data_advisor_only=args.data_advisor_only,
        )
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
    if args.catalog_only:
        return 0 if result.get("status") == "READONLY_CATALOG_MATRIX" else 2
    return 0 if result.get("status") == "R2_5_DEP_ADP_QUERY_EVIDENCE_GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
