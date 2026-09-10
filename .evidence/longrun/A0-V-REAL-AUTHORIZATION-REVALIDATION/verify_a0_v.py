#!/usr/bin/env python3
"""Fail-closed validation for the A0-V readiness evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_RESULT = "A0_V_BLOCKED_WITH_ACTIONABLE_GAPS"
SENSITIVE_VALUE = re.compile(
    r"(?i)(?:bearer\s+(?!<redacted>)[a-z0-9._~+/=-]+|postgres(?:ql)?://[^:/\s]+:[^@/\s]+@)"
)


def _walk(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_walk(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_walk(item, f"{path}[{index}]"))
    elif isinstance(value, str) and SENSITIVE_VALUE.search(value):
        errors.append(f"sensitive value at {path}")
    return errors


def verify(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if document.get("result") != EXPECTED_RESULT:
        errors.append(f"result must remain {EXPECTED_RESULT} while blockers exist")

    scope = document.get("scope") or {}
    if scope.get("baseUrl") != "http://127.0.0.1:18181":
        errors.append("baseUrl must be the fixed loopback AOS API")
    if scope.get("httpMethods") != ["GET"]:
        errors.append("httpMethods must contain GET only")
    if scope.get("positive") != {"orgId": "org-org", "projectId": "dev-project"}:
        errors.append("positive tenant mismatch")
    if scope.get("canary") != {"orgId": "dev-org", "projectId": "dev-project"}:
        errors.append("canary tenant mismatch")
    guards = scope.get("runtimeGuards") or {}
    for name in ("migrationMode", "qyhCron", "logicAutomation", "providerHealthMaintenance"):
        if guards.get(name) not in {"disabled", "inactive"}:
            errors.append(f"runtime guard not disabled: {name}")

    summary = document.get("summary") or {}
    blockers = summary.get("blockers") or []
    unverified = summary.get("unverified") or []
    if summary.get("blockerCount") != len(blockers):
        errors.append("blockerCount mismatch")
    if summary.get("unverifiedCount") != len(unverified):
        errors.append("unverifiedCount mismatch")
    if not blockers:
        errors.append("current recovery baseline must not be promoted without blockers")

    blocker_gates = {
        item.get("gate") for item in blockers if isinstance(item, dict)
    }

    observations = document.get("observations") or {}
    for group_name, group in observations.items():
        entries = group if isinstance(group, dict) and "method" not in group else {group_name: group}
        for name, entry in entries.items():
            if not isinstance(entry, dict) or entry.get("method") != "GET":
                errors.append(f"non-GET or malformed observation: {group_name}.{name}")
    negative = observations.get("negative") or {}
    if (negative.get("missingBearer") or {}).get("httpStatus") != 401:
        errors.append("missing Bearer check must return 401")
    if (negative.get("invalidLimit") or {}).get("httpStatus") not in {400, 422}:
        errors.append("invalid limit check must return 400 or 422")

    positive = observations.get("positive") or {}
    for name in ("sourceReadiness", "workshopSourceReadiness"):
        observation = positive.get(name) or {}
        body = observation.get("body") or {}
        status = body.get("status") if isinstance(body, dict) else None
        if observation.get("httpStatus") == 200 and status != "ready":
            if f"{name}.status" not in blocker_gates:
                errors.append(f"blocked {name} status must remain a blocker")

    agent = positive.get("agentRegistry") or {}
    if agent.get("httpStatus") == 200:
        body = agent.get("body") or {}
        stats = body.get("stats") if isinstance(body, dict) else {}
        expected = {
            "definitionCount": 6,
            "installedCount": 6,
            "runnableCount": 6,
            "skillDefinitionCount": 37,
            "capabilityDefinitionCount": 10,
        }
        for key, value in expected.items():
            if stats.get(key) != value and f"agentRegistry.stats.{key}" not in blocker_gates:
                errors.append(f"agentRegistry {key} mismatch must remain a blocker")

    dynamic_outputs = {"productionContexts", "productionStartDecisions", "taskBriefs"}
    for gate in dynamic_outputs.intersection(blocker_gates):
        errors.append(f"dynamic A1 output must not be an A0-V non-empty blocker: {gate}")

    for name in ("responsibilityPlans", "stageTemplates"):
        observation = positive.get(name) or {}
        body = observation.get("body") or {}
        items = body.get("items") if isinstance(body, dict) else None
        if observation.get("httpStatus") == 200 and items == []:
            if f"{name}.authority" not in blocker_gates:
                errors.append(f"missing {name} authority must remain a blocker")

    isolation_unverified = any(
        isinstance(item, dict) and item.get("gate") == "crossTenantResourceIsolation"
        for item in unverified
    )
    if not isolation_unverified:
        isolation = observations.get("isolation") or {}
        if (isolation.get("positiveAgentInstance") or {}).get("httpStatus") != 200:
            errors.append("verified isolation requires positive exact AgentInstance 200")
        if (isolation.get("canaryAgentInstance") or {}).get("httpStatus") != 404:
            errors.append("verified isolation requires canary exact AgentInstance 404")

    errors.extend(_walk(document))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    document = json.loads(args.evidence.read_text(encoding="utf-8"))
    errors = verify(document)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(
        "A0_V_EVIDENCE_VALID "
        f"blockers={document['summary']['blockerCount']} "
        f"unverified={document['summary']['unverifiedCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
