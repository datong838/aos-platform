#!/usr/bin/env python3
"""Audit the exact A0-V ecommerce Agent runtime dependency chain without writes."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
FIRST_INSTALLER = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
AGENT_IDS = (
    "ecommerce.campaign_planner",
    "ecommerce.content_officer",
    "ecommerce.customer_service",
    "ecommerce.data_advisor",
    "ecommerce.private_domain_manager",
    "ecommerce.shopping_advisor",
)
INSTANCE_IDS = tuple(f"{item}.default" for item in AGENT_IDS)
LOGIC_IDS = (
    *(f"D{i:02d}" for i in range(1, 7)),
    *(f"C{i:02d}" for i in range(1, 9)),
    *(f"G{i:02d}" for i in range(1, 7)),
    *(f"S{i:02d}" for i in range(1, 7)),
    *(f"P{i:02d}" for i in range(1, 6)),
    *(f"A{i:02d}" for i in range(1, 7)),
)
SKILL_IDS = tuple(f"ecommerce.skill.{item}" for item in LOGIC_IDS)
CAPABILITY_IDS = (
    "material.collect",
    "strategy.plan",
    "copy.generate",
    "script.compose",
    "speech.synthesize",
    "video.compose",
    "content.review",
    "live.orchestrate",
    "platform.adapt",
    "performance.review",
)
CONFIGURATION_IDS = {
    "egress": "a0v-ecommerce-egress-v1",
    "data": "a0v-ecommerce-public-catalog-v1",
    "network": "a0v-ecommerce-network-v1",
    "budget": "a0v-ecommerce-hard-stop-budget-v1",
    "quota": "a0v-ecommerce-quota-v1",
    "budgetPolicy": "a0v-ecommerce-budget-policy-v1",
    "runtimePolicy": "a0v-ecommerce-runtime-policy-v1",
}


class RuntimeReadinessAuditBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default="colima-aos-extension")
    parser.add_argument("--database-container", default="aos-a0v-recovery-pg")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _load_first_installer() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_first_install", FIRST_INSTALLER)
    if spec is None or spec.loader is None:
        raise RuntimeReadinessAuditBlocked("FIRST_INSTALLER_UNAVAILABLE", str(FIRST_INSTALLER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status_counts(rows: list[Any], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row[field])
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _layer(expected: int, actual: int, blockers: list[str] | None = None) -> dict[str, Any]:
    reasons = sorted(set(blockers or []))
    return {
        "expected": expected,
        "actual": actual,
        "status": "ready" if actual == expected and not reasons else "blocked",
        "blockers": reasons,
    }


def summarize(snapshot: dict[str, Any]) -> dict[str, Any]:
    if any(int(value) for value in snapshot["canaryCounts"].values()):
        raise RuntimeReadinessAuditBlocked(
            "CANARY_RUNTIME_AUTHORITY_NOT_EMPTY", str(snapshot["canaryCounts"])
        )
    layers = {
        "agentTemplates": _layer(6, snapshot["publishedAgentTemplateCount"]),
        "evaluatedSkills": _layer(37, snapshot["evaluatedSkillCount"]),
        "capabilityDefinitions": _layer(10, snapshot["publishedCapabilityCount"]),
        "configurationPolicies": _layer(7, snapshot["configurationPolicyCount"]),
        "capabilityEvalAndW0b": _layer(
            10,
            snapshot["capabilityEvalAndW0bReadyCount"],
            snapshot["capabilityEvalAndW0bBlockers"],
        ),
        "providers": _layer(1, min(snapshot["activeProviderCount"], 1), [
            "provider_instance_unavailable"
        ] if snapshot["activeProviderCount"] < 1 else []),
        "providerHealth": _layer(1, min(snapshot["healthyProviderObservationCount"], 1), [
            "current_provider_health_unavailable"
        ] if snapshot["healthyProviderObservationCount"] < 1 else []),
        "modelRoutes": _layer(1, min(snapshot["activeModelRouteCount"], 1)),
        "capabilityProviderRoute": _layer(
            10,
            snapshot["capabilityProviderRouteReadyCount"],
            snapshot["capabilityProviderRouteBlockers"],
        ),
        "evalContracts": _layer(37, snapshot["frozenEvalContractCount"]),
        "evalGates": _layer(37, snapshot["currentPassedEvalGateCount"]),
        "logicPublications": _layer(37, snapshot["logicPublicationCount"]),
        "publishedSkills": _layer(37, snapshot["publishedSkillCount"]),
        "capabilityBindings": _layer(10, snapshot["freshCapabilityBindingCount"]),
        "skillBindings": _layer(37, snapshot["freshSkillBindingCount"]),
        "activeAgentInstances": _layer(6, snapshot["activeAgentInstanceCount"]),
        "responsibilityPlan": _layer(1, min(snapshot["frozenResponsibilityPlanCount"], 1)),
    }
    priority = (
        ("agentTemplates", "REPAIR_CANONICAL_AGENT_DEFINITIONS"),
        ("evaluatedSkills", "REPAIR_CANONICAL_SKILL_DEFINITIONS"),
        ("capabilityDefinitions", "REPAIR_CANONICAL_CAPABILITY_DEFINITIONS"),
        ("configurationPolicies", "REPAIR_CURRENT_CONFIGURATION_POLICIES"),
        ("capabilityEvalAndW0b", "MATERIALIZE_CAPABILITY_EVAL_AND_W0B_AUTHORITY"),
        ("providers", "ESTABLISH_REAL_PROVIDER_INSTANCE_AUTHORITY"),
        ("providerHealth", "VERIFY_REAL_PROVIDER_HEALTH"),
        ("modelRoutes", "ACTIVATE_EXACT_MODEL_ROUTE"),
        ("capabilityProviderRoute", "BIND_CAPABILITY_DEFINITIONS_TO_EXACT_PROVIDER_ROUTE"),
        ("evalContracts", "FREEZE_EXACT_SKILL_EVAL_CONTRACTS"),
        ("evalGates", "PASS_EXACT_SKILL_RELEASE_GATES"),
        ("logicPublications", "PUBLISH_EXACT_LOGIC_REVISIONS"),
        ("publishedSkills", "PUBLISH_EVALUATED_SKILLS"),
        ("capabilityBindings", "CREATE_EVALUATE_AND_ACTIVATE_CAPABILITY_BINDINGS"),
        ("skillBindings", "CREATE_EVALUATE_AND_ACTIVATE_SKILL_BINDINGS"),
        ("activeAgentInstances", "ACTIVATE_SIX_AGENT_INSTANCES"),
        ("responsibilityPlan", "FREEZE_RESPONSIBILITY_PLAN"),
    )
    first_gate = None
    next_action = "REVALIDATE_CURRENT_FOUR_SOURCE_CONFIGURATION"
    for gate, action in priority:
        if layers[gate]["status"] != "ready":
            first_gate, next_action = gate, action
            break
    return {
        "outcome": (
            "A0V_AGENT_RUNTIME_READINESS_GREEN"
            if first_gate is None
            else "A0V_AGENT_RUNTIME_READINESS_BLOCKED"
        ),
        "layers": layers,
        "firstUnsatisfiedGate": first_gate,
        "nextAction": next_action,
    }


def audit(connect: Any, *, observed_at: datetime) -> dict[str, Any]:
    with connect() as conn:
        identity = conn.execute("SELECT current_database() AS database").fetchone()
        if identity is None or identity["database"] != "aos_meta_head":
            raise RuntimeReadinessAuditBlocked("DATABASE_IDENTITY_MISMATCH", str(identity))
        templates = conn.execute(
            "SELECT template_id,lifecycle FROM aip_agent_template_revision WHERE template_id=ANY(%s)",
            (list(AGENT_IDS),),
        ).fetchall()
        instances = conn.execute(
            "SELECT instance_id,status FROM aip_agent_instance WHERE org_id=%s AND project_id=%s AND instance_id=ANY(%s)",
            (ORG_ID, PROJECT_ID, list(INSTANCE_IDS)),
        ).fetchall()
        skills = conn.execute(
            "SELECT skill_id,lifecycle FROM aip_skill_template_revision WHERE skill_id=ANY(%s)",
            (list(SKILL_IDS),),
        ).fetchall()
        capabilities = conn.execute(
            "SELECT capability_id,lifecycle,readiness,readiness_reasons FROM aip_capability_revision WHERE capability_id=ANY(%s)",
            (list(CAPABILITY_IDS),),
        ).fetchall()
        row = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM aip_provider_instance_revision WHERE org_id=%s AND project_id=%s AND lifecycle='active') AS active_providers,
              (SELECT count(*) FROM aip_provider_health_observation WHERE org_id=%s AND project_id=%s AND status='healthy' AND observed_at<=%s AND expires_at>%s) AS healthy_provider_observations,
              (SELECT count(*) FROM aip_model_route_revision WHERE org_id=%s AND project_id=%s AND lifecycle='active') AS active_routes,
              (SELECT count(*) FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND lifecycle='frozen') AS frozen_eval_contracts,
              (SELECT count(*) FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND status='passed' AND decided_at<=%s AND expires_at>%s) AS current_passed_gates,
              (SELECT count(DISTINCT graph_id) FROM aip_logic_publication WHERE org_id=%s AND project_id=%s AND graph_id LIKE 'ecommerce.logic.%%') AS logic_publications,
              (SELECT count(*) FROM aip_capability_binding WHERE org_id=%s AND project_id=%s AND status='active' AND health='healthy' AND operational_readiness='available' AND readiness_expires_at>%s) AS fresh_capability_bindings,
              (SELECT count(*) FROM aip_skill_binding WHERE org_id=%s AND project_id=%s AND status='active' AND readiness='available' AND readiness_expires_at>%s) AS fresh_skill_bindings,
              (SELECT count(*) FROM aip_responsibility_plan_head h JOIN aip_responsibility_plan_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.plan_id=h.plan_id AND r.revision=h.current_revision WHERE h.org_id=%s AND h.project_id=%s AND r.lifecycle='frozen') AS frozen_responsibility_plans
            """,
            (
                ORG_ID, PROJECT_ID,
                ORG_ID, PROJECT_ID, observed_at, observed_at,
                ORG_ID, PROJECT_ID,
                ORG_ID, PROJECT_ID,
                ORG_ID, PROJECT_ID, observed_at, observed_at,
                ORG_ID, PROJECT_ID,
                ORG_ID, PROJECT_ID, observed_at,
                ORG_ID, PROJECT_ID, observed_at,
                ORG_ID, PROJECT_ID,
            ),
        ).fetchone()
        config = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM aip_runtime_guard_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind='egress' AND policy_id=%s) +
              (SELECT count(*) FROM aip_runtime_guard_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind='data_classification' AND policy_id=%s) +
              (SELECT count(*) FROM aip_network_policy_head WHERE org_id=%s AND project_id=%s AND policy_id=%s) +
              (SELECT count(*) FROM aip_budget_head WHERE org_id=%s AND project_id=%s AND budget_id=%s) +
              (SELECT count(*) FROM aip_model_governance_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind='quota' AND policy_id=%s) +
              (SELECT count(*) FROM aip_model_governance_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s) +
              (SELECT count(*) FROM aip_runtime_policy_head WHERE org_id=%s AND project_id=%s AND runtime_policy_id=%s) AS count
            """,
            (
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["egress"],
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["data"],
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["network"],
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["budget"],
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["quota"],
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["budgetPolicy"],
                ORG_ID, PROJECT_ID, CONFIGURATION_IDS["runtimePolicy"],
            ),
        ).fetchone()
        canary = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM aip_agent_instance WHERE org_id=%s AND project_id=%s) AS agent_instances,
              (SELECT count(*) FROM aip_skill_binding WHERE org_id=%s AND project_id=%s) AS skill_bindings,
              (SELECT count(*) FROM aip_capability_binding WHERE org_id=%s AND project_id=%s) AS capability_bindings,
              (SELECT count(*) FROM aip_provider_instance_revision WHERE org_id=%s AND project_id=%s) AS providers,
              (SELECT count(*) FROM aip_model_route_revision WHERE org_id=%s AND project_id=%s) AS routes,
              (SELECT count(*) FROM aip_runtime_policy_head WHERE org_id=%s AND project_id=%s) AS runtime_policies,
              (SELECT count(*) FROM aip_responsibility_plan_head WHERE org_id=%s AND project_id=%s) AS responsibility_plans
            """,
            (CANARY_ORG_ID, CANARY_PROJECT_ID) * 7,
        ).fetchone()
    capability_blockers = sorted({
        reason
        for item in capabilities
        for reason in (item["readiness_reasons"] or [])
        if item["lifecycle"] == "published" and item["readiness"] != "available"
    })
    eval_w0b_reasons = {"eval_pack_unavailable", "w0b_contracts_unavailable"}
    provider_route_reasons = {"provider_unknown", "aip7_route_authority_unavailable"}
    capability_eval_w0b_ready = sum(
        item["lifecycle"] == "published"
        and not (set(item["readiness_reasons"] or []) & eval_w0b_reasons)
        for item in capabilities
    )
    capability_provider_route_ready = sum(
        item["lifecycle"] == "published"
        and not (set(item["readiness_reasons"] or []) & provider_route_reasons)
        for item in capabilities
    )
    snapshot = {
        "publishedAgentTemplateCount": len({item["template_id"] for item in templates if item["lifecycle"] == "published"}),
        "evaluatedSkillCount": len({item["skill_id"] for item in skills if item["lifecycle"] == "evaluated"}),
        "publishedSkillCount": len({item["skill_id"] for item in skills if item["lifecycle"] == "published"}),
        "publishedCapabilityCount": len({item["capability_id"] for item in capabilities if item["lifecycle"] == "published"}),
        "capabilityDefinitionBlockers": capability_blockers,
        "capabilityEvalAndW0bReadyCount": capability_eval_w0b_ready,
        "capabilityEvalAndW0bBlockers": sorted(set(capability_blockers) & eval_w0b_reasons),
        "capabilityProviderRouteReadyCount": capability_provider_route_ready,
        "capabilityProviderRouteBlockers": sorted(set(capability_blockers) & provider_route_reasons),
        "configurationPolicyCount": int(config["count"]),
        "activeProviderCount": int(row["active_providers"]),
        "healthyProviderObservationCount": int(row["healthy_provider_observations"]),
        "activeModelRouteCount": int(row["active_routes"]),
        "frozenEvalContractCount": int(row["frozen_eval_contracts"]),
        "currentPassedEvalGateCount": int(row["current_passed_gates"]),
        "logicPublicationCount": int(row["logic_publications"]),
        "freshCapabilityBindingCount": int(row["fresh_capability_bindings"]),
        "freshSkillBindingCount": int(row["fresh_skill_bindings"]),
        "activeAgentInstanceCount": sum(item["status"] == "active" for item in instances),
        "agentInstanceStatusCounts": _status_counts(instances, "status"),
        "skillLifecycleCounts": _status_counts(skills, "lifecycle"),
        "canaryCounts": {key: int(canary[key]) for key in canary.keys()},
        "frozenResponsibilityPlanCount": int(row["frozen_responsibility_plans"]),
    }
    return snapshot


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.database_name != "aos_meta_head":
        raise RuntimeReadinessAuditBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED", "aos_meta_head")
    installer = _load_first_installer()
    connect = installer.container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    observed_at = datetime.now(UTC)
    snapshot = audit(connect, observed_at=observed_at)
    result = summarize(snapshot)
    return {
        **result,
        "mode": "read-only-audit",
        "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
        "databaseName": "aos_meta_head",
        "observedAt": observed_at.isoformat(),
        "inventory": snapshot,
        "effects": {
            "mutationCount": 0,
            "providerInvocationCount": 0,
            "externalPublicationCount": 0,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
    except RuntimeReadinessAuditBlocked as exc:
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
