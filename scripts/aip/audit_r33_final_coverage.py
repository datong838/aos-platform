#!/usr/bin/env python3
"""Build the R33 structural coverage matrix without runtime side effects.

This audit deliberately reads only versioned bundle/code authority.  It proves
that the declared ecommerce surface is complete and internally referentially
sound; it does not promote static declarations to operational readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_AGENT_IDS = {
    "ecommerce.data_advisor",
    "ecommerce.private_domain_manager",
    "ecommerce.shopping_advisor",
    "ecommerce.content_officer",
    "ecommerce.customer_service",
    "ecommerce.campaign_planner",
}
EXPECTED_LOGIC_IDS = {
    *(f"D{index:02d}" for index in range(1, 7)),
    *(f"C{index:02d}" for index in range(1, 9)),
    *(f"G{index:02d}" for index in range(1, 7)),
    *(f"S{index:02d}" for index in range(1, 7)),
    *(f"P{index:02d}" for index in range(1, 6)),
    *(f"A{index:02d}" for index in range(1, 7)),
}
EXPECTED_CAPABILITY_IDS = {
    "material.collect",
    "strategy.plan",
    "copy.generate",
    "script.compose",
    "speech.synthesize",
    "video.compose",
    "platform.adapt",
    "content.review",
    "live.orchestrate",
    "performance.review",
}
EXPECTED_PIPELINE_KINDS = {
    "seed_import",
    "operational_learning",
    "network_learning",
    "competitor_analysis",
    "professional_database",
    "customer_feedback",
    "human_experience",
}
EXPECTED_HARNESS_IDS = {
    *(f"DY-{index:02d}" for index in range(1, 6)),
    *(f"KS-{index:02d}" for index in range(1, 4)),
    *(f"SPH-{index:02d}" for index in range(1, 4)),
    *(f"XHS-{index:02d}" for index in range(1, 4)),
}
EXPECTED_SCENARIO_IDS = {f"SC{index:02d}" for index in range(1, 10)}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact(actual: set[str], expected: set[str], label: str) -> None:
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        raise ValueError(f"{label} mismatch: missing={missing}, unexpected={unexpected}")


def build_report(repo_root: Path, *, checked_at: str) -> dict[str, Any]:
    api_root = repo_root / "services" / "aos-api"
    sys.path.insert(0, str(api_root))
    from aos_api.aip_fde_reflection import REFLECTION_RULES, RULE_SET_HASH, RULE_SET_REF
    from aos_api.aip_memory_pipeline_contracts import KnowledgePipelineKind

    content = repo_root / "bundles" / "solutions" / "ecommerce-growth" / "content"
    source_paths = {
        "agents": content / "agents" / "ecommerce-six-coworkers.json",
        "capabilities": content / "agents" / "ecommerce-capability-catalog.json",
        "logics": content / "logic" / "ecommerce-37-logic-catalog.json",
        "harnesses": content / "harness" / "platform-harnesses.v1.json",
        "scenarios01to03": content / "growth" / "sc01-sc03-acceptance.v1.json",
        "scenarios04to06": content / "growth" / "sc04-sc06-acceptance.v1.json",
        "scenarios07to09": content / "growth" / "sc07-sc09-acceptance.v1.json",
    }
    sources = {name: _load(path) for name, path in source_paths.items()}

    agents = sources["agents"]["agents"]
    capabilities = sources["capabilities"]["capabilities"]
    logics = sources["logics"]["logics"]
    harnesses = sources["harnesses"]["harnesses"]
    scenarios: dict[str, Any] = {}
    for key in ("scenarios01to03", "scenarios04to06", "scenarios07to09"):
        overlap = scenarios.keys() & sources[key]["scenarios"].keys()
        if overlap:
            raise ValueError(f"scenario ID duplicated: {sorted(overlap)}")
        scenarios.update(sources[key]["scenarios"])

    agent_ids = {row["id"] for row in agents}
    capability_ids = {row["id"] for row in capabilities}
    logic_ids = {row["id"] for row in logics}
    pipeline_kinds = {kind.value for kind in KnowledgePipelineKind}
    reflection_keys = {rule.rule_key for rule in REFLECTION_RULES}
    harness_ids = {row["harnessId"] for row in harnesses}
    scenario_ids = set(scenarios)

    _exact(agent_ids, EXPECTED_AGENT_IDS, "agent IDs")
    _exact(capability_ids, EXPECTED_CAPABILITY_IDS, "capability IDs")
    _exact(logic_ids, EXPECTED_LOGIC_IDS, "logic IDs")
    _exact(pipeline_kinds, EXPECTED_PIPELINE_KINDS, "pipeline kinds")
    _exact(harness_ids, EXPECTED_HARNESS_IDS, "harness IDs")
    _exact(scenario_ids, EXPECTED_SCENARIO_IDS, "scenario IDs")
    if len(reflection_keys) != 26 or len(REFLECTION_RULES) != 26:
        raise ValueError("reflection rules must contain 26 unique rule keys")

    agent_logic_ids = [logic_id for agent in agents for logic_id in agent["logicIds"]]
    if len(agent_logic_ids) != len(set(agent_logic_ids)):
        raise ValueError("logic ID assigned to more than one agent")
    _exact(set(agent_logic_ids), logic_ids, "agent logic assignments")

    invalid_logic_agents = sorted({row["agentId"] for row in logics} - agent_ids)
    invalid_logic_capabilities = sorted(
        {capability for row in logics for capability in row["capabilities"]} - capability_ids
    )
    invalid_harness_logics = sorted({row["logicId"] for row in harnesses} - logic_ids)
    invalid_harness_capabilities = sorted(
        {capability for row in harnesses for capability in row["requiredCapabilities"]}
        - capability_ids
    )
    invalid_scenario_logics = sorted(
        {logic_id for scenario in scenarios.values() for logic_id in scenario["logicIds"]}
        - logic_ids
    )
    reference_errors = {
        "logicAgentRefs": invalid_logic_agents,
        "logicCapabilityRefs": invalid_logic_capabilities,
        "harnessLogicRefs": invalid_harness_logics,
        "harnessCapabilityRefs": invalid_harness_capabilities,
        "scenarioLogicRefs": invalid_scenario_logics,
    }
    if any(reference_errors.values()):
        raise ValueError(f"invalid cross references: {reference_errors}")

    unverified_rule_authority = sorted(
        row["harnessId"]
        for row in harnesses
        if row.get("ruleAuthority", {}).get("sourceStatus") != "verified"
        or not row.get("ruleAuthority", {}).get("sourceRef")
        or not row.get("ruleAuthority", {}).get("contentHash")
    )
    scenario_statuses = sorted(
        {sources[key]["status"] for key in ("scenarios01to03", "scenarios04to06", "scenarios07to09")}
    )

    dimensions = [
        {"id": "agents", "expected": 6, "actual": len(agent_ids), "structuralStatus": "CODE_GREEN", "operationalStatus": sources["agents"]["runtimeReadiness"].upper()},
        {"id": "logics", "expected": 37, "actual": len(logic_ids), "structuralStatus": "CODE_GREEN", "operationalStatus": sources["logics"]["readiness"].upper()},
        {"id": "capabilities", "expected": 10, "actual": len(capability_ids), "structuralStatus": "CODE_GREEN", "operationalStatus": sources["capabilities"]["readiness"].upper()},
        {"id": "knowledgePipelines", "expected": 7, "actual": len(pipeline_kinds), "structuralStatus": "CODE_GREEN", "operationalStatus": "BLOCKED_EXTERNAL", "reason": "R16 evidence records unconfigured schedules and external-data gate"},
        {"id": "reflectionRules", "expected": 26, "actual": len(reflection_keys), "structuralStatus": "CODE_GREEN", "operationalStatus": "CODE_CONTROL_ONLY", "ruleSetRef": RULE_SET_REF, "ruleSetHash": RULE_SET_HASH},
        {"id": "platformHarnesses", "expected": 14, "actual": len(harness_ids), "structuralStatus": "CODE_GREEN", "operationalStatus": "BLOCKED_EXTERNAL", "unverifiedRuleAuthorityCount": len(unverified_rule_authority)},
        {"id": "scenarios", "expected": 9, "actual": len(scenario_ids), "structuralStatus": "CODE_GREEN", "operationalStatus": "BLOCKED_EXTERNAL", "declaredStatuses": scenario_statuses},
    ]

    return {
        "schemaVersion": "aip.r33.coverage-matrix.v1",
        "checkedAt": checked_at,
        "scope": {"branch": "w1-aip", "tenant": "org-org/dev-project", "negativeCanary": "dev-org/dev-project", "mode": "STATIC_READ_ONLY"},
        "verdict": "STRUCTURAL_GREEN_OPERATIONAL_BLOCKED",
        "dimensions": dimensions,
        "referenceErrors": reference_errors,
        "blockers": {
            "staticRuntimeReadiness": {
                "agents": sources["agents"]["runtimeReadiness"],
                "logics": sources["logics"]["readiness"],
                "capabilities": sources["capabilities"]["readiness"],
            },
            "unverifiedHarnessRuleAuthorityIds": unverified_rule_authority,
            "scenarioStatuses": scenario_statuses,
            "knowledgePipelines": "EXTERNAL_DATA_GATED",
        },
        "sourceRefs": {
            name: {"path": str(path.relative_to(repo_root)), "sha256": _sha256(path)}
            for name, path in source_paths.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--checked-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.repo_root.resolve(), checked_at=args.checked_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
