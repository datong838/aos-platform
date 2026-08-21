#!/usr/bin/env python3
"""Compose C01/C03-C08 Content Officer bindings without starting AgentRun."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap_r10_campaign_planner_binding_authority as _base

SCOPE = _base.SCOPE
CANARY_SCOPE = _base.CANARY_SCOPE
ACTOR = "aip-r11-content-officer-binding-bootstrap"
INSTANCE_ID = "ecommerce.content_officer.default"
C02_BINDING_ID = "ecommerce.content_officer.skill.C02.r2"

BINDING_SPECS = {
    "C01": ["ecommerce.shared.material.collect.r1"],
    "C03": ["ecommerce.shared.copy.generate.r1"],
    "C04": ["ecommerce.shared.script.compose.r1"],
    "C05": ["ecommerce.shared.platform.adapt.r1"],
    "C06": ["ecommerce.shared.content.review.r1"],
    "C07": [
        "ecommerce.shared.material.collect.r1",
        "ecommerce.shared.copy.generate.r1",
    ],
    "C08": ["ecommerce.shared.performance.review.r1"],
}


def _configure_base() -> None:
    _base.ACTOR = ACTOR
    _base.INSTANCE_ID = INSTANCE_ID
    _base.A02_BINDING_ID = C02_BINDING_ID
    _base.BINDING_SPECS = BINDING_SPECS
    _base.binding_id = binding_id


def binding_id(logic_id: str) -> str:
    return f"ecommerce.content_officer.skill.{logic_id}.r2"


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "instanceId": INSTANCE_ID,
        "preservedAuthority": [C02_BINDING_ID],
        "bindings": [
            {
                "logicId": logic_id,
                "bindingId": binding_id(logic_id),
                "skill": f"ecommerce.skill.{logic_id}@r2",
                "capabilityBindingIds": capability_ids,
            }
            for logic_id, capability_ids in BINDING_SPECS.items()
        ],
        "providerCalls": 0,
        "agentRuns": 0,
        "externalContentActions": 0,
        "mediaGenerations": 0,
        "memoryPromotions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def _snapshot_c02(registry: Any) -> dict[str, Any]:
    item = registry.get_binding(SCOPE, C02_BINDING_ID)
    return item.model_dump(mode="json", by_alias=True)


def _apply_configured(*, now: datetime | None = None) -> dict[str, Any]:
    _base._require_schema_head()
    evaluated_at = now or datetime.now(UTC)
    canary_before = _base._counts(CANARY_SCOPE)
    if canary_before["skillBindings"]:
        raise _base.BindingCompositionBlocked("NEGATIVE_CANARY_NOT_EMPTY")

    instance = _base.AipAgentRegistryStore().get_instance(SCOPE, INSTANCE_ID)
    if instance.status.value != "active":
        raise _base.BindingCompositionBlocked("CONTENT_OFFICER_INSTANCE_NOT_ACTIVE")
    policy = _base.AipModelRuntimeStore().get_policy(
        SCOPE, _base.POLICY_ID, _base.POLICY_REVISION
    )
    registry = _base.AipSkillRegistry()
    c02_before = _snapshot_c02(registry)
    results = [
        _base._ensure_binding(
            registry,
            logic_id=logic_id,
            budget_policy_ref=policy.budget_policy_ref,
            evaluated_at=evaluated_at,
        )
        for logic_id in BINDING_SPECS
    ]

    c02_after = _snapshot_c02(registry)
    if c02_after != c02_before:
        raise _base.BindingCompositionBlocked("IMMUTABLE_C02_BINDING_CHANGED")
    canary_after = _base._counts(CANARY_SCOPE)
    if canary_after != canary_before:
        raise _base.BindingCompositionBlocked("NEGATIVE_CANARY_CHANGED")
    runtime_tail = sorted(
        {reason for item in results for reason in item.readiness_reasons}
    )
    active_count = sum(item.status == "active" for item in results)
    return {
        "status": (
            "R11_CONTENT_OFFICER_BINDING_GREEN"
            if active_count == len(results)
            else "R11_CONTENT_OFFICER_BINDING_GREEN_WITH_RUNTIME_TAIL"
        ),
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "instance": {"instanceId": INSTANCE_ID, "status": instance.status.value},
        "bindings": [
            {
                "bindingId": item.binding_id,
                "skill": item.skill.model_dump(mode="json", by_alias=True),
                "status": item.status,
                "readiness": item.readiness.value,
                "readinessReasons": item.readiness_reasons,
                "capabilityBindingIds": item.capability_binding_ids,
            }
            for item in results
        ],
        "activeCount": active_count,
        "runtimeTail": runtime_tail,
        "preservedC02": c02_after,
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "externalContentActions": 0,
        "mediaGenerations": 0,
        "memoryPromotions": 0,
        "productionActions": 0,
        "secretPayloadReads": 0,
    }


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    original = {
        "ACTOR": _base.ACTOR,
        "INSTANCE_ID": _base.INSTANCE_ID,
        "A02_BINDING_ID": _base.A02_BINDING_ID,
        "BINDING_SPECS": _base.BINDING_SPECS,
        "binding_id": _base.binding_id,
    }
    _configure_base()
    try:
        return _apply_configured(now=now)
    finally:
        for name, value in original.items():
            setattr(_base, name, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else build_plan()
    except _base.BindingCompositionBlocked as exc:
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
