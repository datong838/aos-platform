#!/usr/bin/env python3
"""Build the tenant-scoped R12 ecommerce 37-logic readiness matrix.

The audit is deliberately read-only.  It distinguishes the canonical 37 logic
catalog from revision rows, specialty pilots, and expanded binding rows.  A
stored ``available`` value is never accepted after its readiness TTL expires.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = ROOT / "services/aos-api"
CATALOG_PATH = (
    ROOT
    / "bundles/solutions/ecommerce-growth/content/logic/ecommerce-37-logic-catalog.json"
)
API_DEFAULT = "http://127.0.0.1:8080/v1/aip"
ORG_DEFAULT = "org-org"
PROJECT_DEFAULT = "dev-project"
CANARY_ORG = "dev-org"
SPECIALTY_PREFIXES = ("I", "V")

sys.path.insert(0, str(SERVICE_ROOT))


def _parse_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _asset_id(ref: Any) -> str | None:
    return ref.get("assetId") if isinstance(ref, dict) else None


def _exact_ref(ref: Any, expected_type: str | None = None) -> bool:
    if not isinstance(ref, dict):
        return False
    if expected_type and ref.get("assetType") != expected_type:
        return False
    revision = ref.get("revision")
    return bool(ref.get("assetId") and revision is not None and ref.get("contentHash"))


def _latest_published(items: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    published = [item for item in items if item.get("lifecycle") == "published"]
    if not published:
        return None
    return max(published, key=lambda item: int(item.get("revision") or 0))


def _fresh_available(
    state: str | None, expiry: str | datetime | None, now: datetime
) -> tuple[bool, str | None]:
    if state != "available":
        return False, "READINESS_NOT_AVAILABLE"
    parsed = _parse_time(expiry)
    if parsed is None:
        return False, "READINESS_EXPIRY_MISSING"
    if parsed <= now:
        return False, "STALE_READINESS_TTL"
    return True, None


def _logic_suffix(skill_id: str) -> str:
    return skill_id.rsplit(".", 1)[-1]


def build_matrix(
    *,
    catalog: dict[str, Any],
    skills: list[dict[str, Any]],
    runtime: dict[str, Any],
    agents: list[dict[str, Any]],
    logic_graphs: dict[str, dict[str, Any]],
    logic_publications: dict[str, dict[str, Any]],
    now: datetime,
    expected_canonical_count: int = 37,
) -> dict[str, Any]:
    """Return a deterministic matrix without performing I/O or writes."""
    canonical = catalog.get("logics") or []
    canonical_ids = {str(item["id"]) for item in canonical}
    canonical_skill_ids = {f"ecommerce.skill.{logic_id}" for logic_id in canonical_ids}

    skill_revisions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in skills:
        skill_revisions[str(item.get("skillId"))].append(item)
    published_skills = {
        skill_id: _latest_published(items)
        for skill_id, items in skill_revisions.items()
    }
    published_skills = {
        skill_id: item for skill_id, item in published_skills.items() if item is not None
    }

    specialty_skill_ids = sorted(
        skill_id
        for skill_id in published_skills
        if skill_id not in canonical_skill_ids
        and _logic_suffix(skill_id).startswith(SPECIALTY_PREFIXES)
    )
    skill_bindings = runtime.get("skillBindings") or []
    capability_bindings = runtime.get("capabilityBindings") or []
    binding_by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in skill_bindings:
        skill_id = _asset_id(binding.get("skill"))
        if skill_id:
            binding_by_skill[skill_id].append(binding)
    capability_by_id = {
        str(binding.get("bindingId")): binding for binding in capability_bindings
    }
    agent_by_template = {
        str(item.get("template", {}).get("assetId")): item for item in agents
    }

    rows: list[dict[str, Any]] = []
    role_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for definition in canonical:
        short_id = str(definition["id"])
        graph_id = f"ecommerce.logic.{short_id}"
        skill_id = f"ecommerce.skill.{short_id}"
        agent_id = str(definition["agentId"])
        instance_id = f"{agent_id}.default"
        blockers: list[str] = []

        graph = logic_graphs.get(graph_id)
        publication = logic_publications.get(graph_id)
        graph_exact = bool(
            graph
            and publication
            and int(graph.get("revision") or 0)
            == int(publication.get("graph_revision") or 0)
            and graph.get("graph_hash") == publication.get("graph_hash")
        )
        if graph is None:
            blockers.append("LOGIC_GRAPH_MISSING")
        elif publication is None:
            blockers.append("LOGIC_PUBLICATION_MISSING")
        elif not graph_exact:
            blockers.append("LOGIC_PUBLICATION_DRIFT")

        skill = published_skills.get(skill_id)
        expected_logic_ref = graph_id
        skill_exact = bool(
            skill
            and skill.get("canonicalLogicId") == expected_logic_ref
            and _exact_ref(skill.get("logicRevisionRef"), "LogicRevision")
            and _asset_id(skill.get("logicRevisionRef")) == expected_logic_ref
            and graph
            and skill["logicRevisionRef"].get("revision") == graph.get("revision")
            and skill["logicRevisionRef"].get("contentHash") == graph.get("graph_hash")
            and _exact_ref(skill.get("modelRouteRef"), "ModelRouteRevision")
            and _exact_ref(skill.get("runtimePolicyRef"), "RuntimePolicyRevision")
            and _exact_ref(skill.get("releaseGateRef"), "EvalGateDecision")
        )
        if skill is None:
            blockers.append("PUBLISHED_SKILL_MISSING")
        elif not skill_exact:
            blockers.append("SKILL_EXACT_AUTHORITY_DRIFT")

        bindings = binding_by_skill.get(skill_id, [])
        expected_bindings = [
            item
            for item in bindings
            if item.get("instanceId") == instance_id
            and item.get("status") == "active"
            and skill
            and item.get("skill", {}).get("revision") == skill.get("revision")
            and item.get("skill", {}).get("contentHash") == skill.get("contentHash")
        ]
        binding = max(expected_bindings, key=lambda item: int(item.get("version") or 0)) if expected_bindings else None
        if binding is None:
            blockers.append("ACTIVE_EXACT_SKILL_BINDING_MISSING")

        binding_fresh = False
        capability_ids: set[str] = set()
        capability_binding_ids: list[str] = []
        if binding:
            binding_fresh, freshness_blocker = _fresh_available(
                binding.get("readiness"), binding.get("readinessExpiresAt"), now
            )
            if freshness_blocker:
                blockers.append(freshness_blocker)
            dependencies = binding.get("dependencies") or {}
            if not _exact_ref(dependencies.get("modelRouteRef"), "ModelRouteRevision"):
                blockers.append("BINDING_MODEL_ROUTE_REF_MISSING")
            if not _exact_ref(dependencies.get("runtimePolicyRef"), "RuntimePolicyRevision"):
                blockers.append("BINDING_RUNTIME_POLICY_REF_MISSING")
            if not _exact_ref(dependencies.get("evalGateRef"), "EvalGateDecision"):
                blockers.append("BINDING_EVAL_GATE_REF_MISSING")
            budget_ref = binding.get("budgetPolicyRef") or dependencies.get("budgetPolicyRef")
            if not _exact_ref(budget_ref, "BudgetPolicyRevision"):
                blockers.append("BINDING_BUDGET_POLICY_REF_MISSING")

            capability_binding_ids = list(binding.get("capabilityBindingIds") or [])
            for capability_binding_id in capability_binding_ids:
                capability = capability_by_id.get(capability_binding_id)
                if capability is None:
                    blockers.append(f"CAPABILITY_BINDING_MISSING:{capability_binding_id}")
                    continue
                capability_id = _asset_id(capability.get("capability"))
                if capability_id:
                    capability_ids.add(capability_id)
                capability_fresh, capability_blocker = _fresh_available(
                    capability.get("operationalReadiness"),
                    capability.get("readinessExpiresAt"),
                    now,
                )
                if capability.get("status") != "active":
                    blockers.append(f"CAPABILITY_BINDING_INACTIVE:{capability_binding_id}")
                if not capability_fresh and capability_blocker:
                    blockers.append(f"{capability_blocker}:{capability_binding_id}")
                dependencies = capability.get("dependencies") or {}
                for key, asset_type, code in (
                    ("providerRef", "ProviderInstanceRevision", "PROVIDER_REF_MISSING"),
                    ("modelRouteRef", "ModelRouteRevision", "CAPABILITY_ROUTE_REF_MISSING"),
                    ("runtimePolicyRef", "RuntimePolicyRevision", "CAPABILITY_POLICY_REF_MISSING"),
                    ("evalGateRef", "EvalGateDecision", "CAPABILITY_EVAL_REF_MISSING"),
                    ("budgetPolicyRef", "BudgetPolicyRevision", "CAPABILITY_BUDGET_REF_MISSING"),
                ):
                    if not _exact_ref(dependencies.get(key), asset_type):
                        blockers.append(f"{code}:{capability_binding_id}")
                # Report only whether an opaque reference exists; never expose it.
                if not capability.get("secretRef"):
                    blockers.append(f"SECRET_REF_MISSING:{capability_binding_id}")

        required_capabilities = set(skill.get("requiredCapabilities") or []) if skill else set()
        missing_capabilities = sorted(required_capabilities - capability_ids)
        if missing_capabilities:
            blockers.extend(f"CAPABILITY_NOT_BOUND:{item}" for item in missing_capabilities)

        agent = agent_by_template.get(agent_id)
        instance_active = bool(agent and agent.get("status") == "active")
        if not instance_active:
            blockers.append("ACTIVE_AGENT_INSTANCE_MISSING")

        blockers = sorted(set(blockers))
        row = {
            "logicId": short_id,
            "logicAssetId": graph_id,
            "skillId": skill_id,
            "agentId": agent_id,
            "agentInstanceId": instance_id,
            "graphExactPublished": graph_exact,
            "skillExactPublished": skill_exact,
            "skillRevision": skill.get("revision") if skill else None,
            "bindingId": binding.get("bindingId") if binding else None,
            "bindingVersion": binding.get("version") if binding else None,
            "bindingFresh": binding_fresh,
            "requiredCapabilityIds": sorted(required_capabilities),
            "boundCapabilityIds": sorted(capability_ids),
            "capabilityBindingIds": capability_binding_ids,
            "toolAllowlist": list(skill.get("toolAllowlist") or []) if skill else [],
            "runnable": not blockers,
            "blockers": blockers,
        }
        rows.append(row)
        role_rows[agent_id].append(row)

    role_summary = []
    for agent_id in sorted(role_rows):
        items = role_rows[agent_id]
        agent = agent_by_template.get(agent_id)
        blockers = sorted({blocker for item in items for blocker in item["blockers"]})
        role_summary.append(
            {
                "agentId": agent_id,
                "agentInstanceId": f"{agent_id}.default",
                "instanceActive": bool(agent and agent.get("status") == "active"),
                "canonicalLogicCount": len(items),
                "runnableLogicCount": sum(1 for item in items if item["runnable"]),
                "runnable": bool(items) and not blockers,
                "blockers": blockers,
            }
        )

    canonical_capabilities = sorted(
        {str(cap) for item in canonical for cap in (item.get("capabilities") or [])}
    )
    static_ready = all(
        row["graphExactPublished"]
        and row["skillExactPublished"]
        and row["bindingId"] is not None
        for row in rows
    )
    runtime_ready = all(row["runnable"] for row in rows)
    return {
        "schemaVersion": 1,
        "tenant": {"orgId": ORG_DEFAULT, "projectId": PROJECT_DEFAULT},
        "evaluatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "countSemantics": {
            "canonicalLogicCount": len(canonical_ids),
            "expectedCanonicalLogicCount": expected_canonical_count,
            "canonicalPublishedSkillCount": sum(
                1 for skill_id in canonical_skill_ids if skill_id in published_skills
            ),
            "specialtyPilotSkillCount": len(specialty_skill_ids),
            "specialtyPilotSkillIds": specialty_skill_ids,
            "uniquePublishedSkillCount": len(published_skills),
            "skillRevisionRowCount": len(skills),
            "tenantSkillBindingRowCount": len(skill_bindings),
            "canonicalSkillBindingCount": sum(
                1 for skill_id in canonical_skill_ids if binding_by_skill.get(skill_id)
            ),
            "tenantCapabilityBindingRowCount": len(capability_bindings),
            "canonicalCapabilityClassCount": len(canonical_capabilities),
            "canonicalCapabilityIds": canonical_capabilities,
        },
        "gates": {
            "catalogExactly37": len(canonical_ids) == expected_canonical_count,
            "staticAuthority37of37": static_ready,
            "runtimeRunnable37of37": runtime_ready,
            "sixAgentInstancesRunnable": len(role_summary) == 6
            and all(item["runnable"] for item in role_summary),
        },
        "roles": role_summary,
        "rows": sorted(rows, key=lambda item: item["logicId"]),
    }


def _request_json(url: str, org: str, project: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer dev",
            "X-Org-Id": org,
            "X-Project-Id": project,
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def _load_logic_authority(org: str, project: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(org, project)
    with connect(scope) as conn:
        graph_rows = conn.execute(
            """SELECT DISTINCT ON (graph_id) graph_id, revision, graph_hash
               FROM aip_logic_graph_revision
               WHERE org_id=%s AND project_id=%s
               ORDER BY graph_id, revision DESC""",
            scope.key,
        ).fetchall()
        publication_rows = conn.execute(
            """SELECT DISTINCT ON (graph_id) graph_id, graph_revision, graph_hash,
                      publication_id
               FROM aip_logic_publication
               WHERE org_id=%s AND project_id=%s
               ORDER BY graph_id, graph_revision DESC, created_at DESC""",
            scope.key,
        ).fetchall()
    return (
        {row["graph_id"]: dict(row) for row in graph_rows},
        {row["graph_id"]: dict(row) for row in publication_rows},
    )


def _canary_summary(api: str) -> dict[str, Any]:
    agents = _request_json(f"{api}/agents", CANARY_ORG, PROJECT_DEFAULT)
    runtime = _request_json(
        f"{api}/agent-registry/runtime-readiness", CANARY_ORG, PROJECT_DEFAULT
    )
    payload = json.dumps({"agents": agents, "runtime": runtime}, ensure_ascii=False)
    return {
        "tenant": {"orgId": CANARY_ORG, "projectId": PROJECT_DEFAULT},
        "responseContainsPositiveTenant": ORG_DEFAULT in payload,
        "agentInstanceCount": len(agents.get("items") or []),
        "skillBindingCount": len(runtime.get("skillBindings") or []),
        "capabilityBindingCount": len(runtime.get("capabilityBindings") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=API_DEFAULT)
    parser.add_argument("--org", default=ORG_DEFAULT)
    parser.add_argument("--project", default=PROJECT_DEFAULT)
    parser.add_argument("--now", help="ISO-8601 audit cutoff; defaults to current UTC")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if (args.org, args.project) != (ORG_DEFAULT, PROJECT_DEFAULT):
        raise SystemExit("R12 positive audit is fixed to org-org/dev-project")

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    skills = _request_json(f"{args.api}/skills?limit=200", args.org, args.project).get(
        "items", []
    )
    runtime = _request_json(
        f"{args.api}/agent-registry/runtime-readiness", args.org, args.project
    )
    agents = _request_json(f"{args.api}/agents", args.org, args.project).get("items", [])
    graph_rows, publication_rows = _load_logic_authority(args.org, args.project)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    assert now is not None
    result = build_matrix(
        catalog=catalog,
        skills=skills,
        runtime=runtime,
        agents=agents,
        logic_graphs=graph_rows,
        logic_publications=publication_rows,
        now=now,
    )
    result["negativeCanary"] = _canary_summary(args.api)
    result["gates"]["negativeCanaryIsolated"] = not result["negativeCanary"][
        "responseContainsPositiveTenant"
    ]
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if all(result["gates"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
