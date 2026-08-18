#!/usr/bin/env python3
"""Publish additive D03 Skill r3 onto route r2 without calling Provider.

Default is inspect/dry-run. --apply publishes SkillTemplate r3 from the
evaluated r1 source, creates SkillBinding r3, and evaluates/activates it.
It never starts an AgentRun, never probes Provider health, and never rewrites
Skill r2 or Binding r2.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "aos-api"))

from aos_api.aip_agent_registry_contracts import (  # noqa: E402
    CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest,
    PublishEvaluatedSkillRevisionRequest,
    UpdateSkillBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (  # noqa: E402
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore  # noqa: E402
from aos_api.aip_skill_publication_service import AipSkillPublicationService  # noqa: E402
from aos_api.aip_skill_registry import AipSkillRegistry  # noqa: E402
from aos_api.db import connect as db_connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-4n-skill-route-cascade"
SKILL_ID = "ecommerce.skill.D03"
SOURCE_SKILL_REVISION = 1
HISTORICAL_SKILL_REVISION = 2
TARGET_SKILL_REVISION = 3
SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r3"
HISTORICAL_SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r2"
ROUTE_ID = "route-qyh-text-dev"
PROVIDER_BUSINESS_CALL_LIMIT = 0
HEALTH_PROBE_LIMIT = 0
ALIGN_ERRORS = (
    RuntimeError,
    KeyError,
    ValueError,
    TypeError,
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryTransitionBlocked,
)


def exact_ref(kind: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind,
        assetId=getattr(item, id_attr),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def dump_ref(ref: VersionedAssetRef | None) -> dict[str, Any] | None:
    if ref is None:
        return None
    return ref.model_dump(mode="json", by_alias=True)


def _skill_or_none(revision: int):
    try:
        return AipSkillRegistry().get_skill(SKILL_ID, revision)
    except AipAgentRegistryNotFound:
        return None


def _binding_or_none(scope: TenantScope, binding_id: str):
    try:
        return AipSkillRegistry().get_binding(scope, binding_id)
    except AipAgentRegistryNotFound:
        return None


def _route_head() -> dict[str, int]:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT current_revision, version FROM aip_model_route_head "
            "WHERE org_id=%s AND project_id=%s AND model_route_id=%s",
            (*SCOPE.key, ROUTE_ID),
        ).fetchone()
    if not row:
        raise RuntimeError("model route head missing")
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


def _canary_binding_count() -> int:
    with db_connect(CANARY_SCOPE) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM aip_skill_binding "
                "WHERE org_id=%s AND project_id=%s AND binding_id=%s",
                (*CANARY_SCOPE.key, SKILL_BINDING_ID),
            ).fetchone()["n"]
        )


def _readiness_value(item: Any) -> str | None:
    if item is None:
        return None
    readiness = getattr(item, "readiness", None)
    if readiness is None:
        return None
    return getattr(readiness, "value", str(readiness))


def inspect() -> dict[str, Any]:
    registry = AipSkillRegistry()
    source = registry.get_skill(SKILL_ID, SOURCE_SKILL_REVISION)
    historical = registry.get_skill(SKILL_ID, HISTORICAL_SKILL_REVISION)
    published = _skill_or_none(TARGET_SKILL_REVISION)
    historical_binding = registry.get_binding(SCOPE, HISTORICAL_SKILL_BINDING_ID)
    binding = _binding_or_none(SCOPE, SKILL_BINDING_ID)
    route_head = _route_head()
    route = AipModelRuntimeStore().get_route(SCOPE, ROUTE_ID, route_head["revision"])
    route_ref = exact_ref("ModelRouteRevision", route, "route_id")
    skill_gate = historical.release_gate_ref
    aligned = bool(
        published is not None
        and published.lifecycle.value == "published"
        and published.revision == TARGET_SKILL_REVISION
        and dump_ref(published.model_route_ref) == dump_ref(route_ref)
        and dump_ref(published.release_gate_ref) == dump_ref(skill_gate)
        and binding is not None
        and binding.skill.revision == TARGET_SKILL_REVISION
        and _readiness_value(binding) == "available"
        and dump_ref(binding.dependencies.model_route_ref) == dump_ref(route_ref)
        and dump_ref(binding.dependencies.eval_gate_ref)
        == dump_ref(published.release_gate_ref)
    )
    return {
        "status": "aligned" if aligned else "drift",
        "sourceSkill": {
            "revision": source.revision,
            "lifecycle": source.lifecycle.value,
            "contentHash": source.content_hash,
        },
        "historicalSkill": {
            "revision": historical.revision,
            "route": dump_ref(historical.model_route_ref),
            "releaseGate": dump_ref(historical.release_gate_ref),
        },
        "publishedSkill": None
        if published is None
        else {
            "revision": published.revision,
            "lifecycle": published.lifecycle.value,
            "route": dump_ref(published.model_route_ref),
            "releaseGate": dump_ref(published.release_gate_ref),
        },
        "historicalBinding": {
            "bindingId": historical_binding.binding_id,
            "skillRevision": historical_binding.skill.revision,
            "status": historical_binding.status,
            "readiness": _readiness_value(historical_binding),
            "reasons": list(historical_binding.readiness_reasons),
            "route": dump_ref(historical_binding.dependencies.model_route_ref),
            "evalGate": dump_ref(historical_binding.dependencies.eval_gate_ref),
        },
        "binding": None
        if binding is None
        else {
            "bindingId": binding.binding_id,
            "skillRevision": binding.skill.revision,
            "status": binding.status,
            "version": binding.version,
            "readiness": _readiness_value(binding),
            "reasons": list(binding.readiness_reasons),
            "route": dump_ref(binding.dependencies.model_route_ref),
            "evalGate": dump_ref(binding.dependencies.eval_gate_ref),
        },
        "liveRoute": dump_ref(route_ref),
        "canaryBindingCount": _canary_binding_count(),
        "providerBusinessCalls": PROVIDER_BUSINESS_CALL_LIMIT,
        "healthProbes": HEALTH_PROBE_LIMIT,
    }


def apply() -> dict[str, Any]:
    snapshot = inspect()
    if snapshot["canaryBindingCount"] != 0:
        raise RuntimeError("negative canary already has SkillBinding r3")
    if snapshot["status"] == "aligned":
        return {
            **snapshot,
            "status": "R2_4N_D03_SKILL_PUBLICATION_ROUTE_GATE_ALIGNED",
        }

    registry = AipSkillRegistry()
    source = registry.get_skill(SKILL_ID, SOURCE_SKILL_REVISION)
    historical = registry.get_skill(SKILL_ID, HISTORICAL_SKILL_REVISION)
    historical_binding = registry.get_binding(SCOPE, HISTORICAL_SKILL_BINDING_ID)
    route_head = _route_head()
    route = AipModelRuntimeStore().get_route(SCOPE, ROUTE_ID, route_head["revision"])
    route_ref = exact_ref("ModelRouteRevision", route, "route_id")
    if historical.publication_ref is None or historical.release_gate_ref is None:
        raise RuntimeError("historical Skill r2 is missing publication provenance")
    if historical.logic_revision_ref is None or historical.runtime_policy_ref is None:
        raise RuntimeError("historical Skill r2 is missing logic or policy refs")
    if route_ref.revision < 2:
        raise RuntimeError("live route is not the R2-4I cascade revision")

    published, _ = AipSkillPublicationService().publish_evaluated_revision(
        SCOPE,
        PublishEvaluatedSkillRevisionRequest(
            source_skill=exact_ref("SkillTemplate", source, "skill_id"),
            publication_id=historical.publication_ref.revision,
            release_gate_decision_id=historical.release_gate_ref.asset_id,
            model_route_ref=route_ref,
            runtime_policy_ref=historical.runtime_policy_ref,
            logic_revision_ref=historical.logic_revision_ref,
            idempotency_key="r2-4n-publish-skill-r3",
        ),
        actor=ACTOR,
        occurred_at=datetime.now(UTC),
    )
    if published.revision != TARGET_SKILL_REVISION:
        raise RuntimeError(
            f"published skill revision {published.revision} is not r3"
        )
    if dump_ref(published.model_route_ref) != dump_ref(route_ref):
        raise RuntimeError("published skill r3 did not pin the live route")
    if dump_ref(published.release_gate_ref) != dump_ref(historical.release_gate_ref):
        raise RuntimeError("published skill r3 drifted off the Skill publication gate")

    now = datetime.now(UTC)
    binding = _binding_or_none(SCOPE, SKILL_BINDING_ID)
    if binding is None:
        binding, _ = registry.create_binding(
            SCOPE,
            CreateSkillBindingRequest(
                binding_id=SKILL_BINDING_ID,
                instance_id=historical_binding.instance_id,
                skill=exact_ref("SkillTemplate", published, "skill_id"),
                capability_binding_ids=list(historical_binding.capability_binding_ids),
                budget_policy_ref=historical_binding.budget_policy_ref,
            ),
            idempotency_key="r2-4n-skill-binding-create-r3",
            actor=ACTOR,
            occurred_at=now,
        )

    skill_deps = binding.dependencies.model_copy(
        update={
            "model_route_ref": published.model_route_ref,
            "runtime_policy_ref": published.runtime_policy_ref,
            "eval_gate_ref": published.release_gate_ref,
        }
    )
    if (
        _readiness_value(binding) != "available"
        or dump_ref(binding.dependencies.model_route_ref) != dump_ref(skill_deps.model_route_ref)
        or dump_ref(binding.dependencies.eval_gate_ref) != dump_ref(skill_deps.eval_gate_ref)
    ):
        binding, readiness, _ = registry.evaluate_binding(
            SCOPE,
            SKILL_BINDING_ID,
            EvaluateOperationalBindingRequest(
                expected_version=binding.version,
                dependencies=skill_deps,
            ),
            idempotency_key="r2-4n-skill-binding-evaluate-r3",
            actor=ACTOR,
            evaluated_at=datetime.now(UTC),
        )
        if getattr(readiness.readiness, "value", str(readiness.readiness)) != "available":
            raise RuntimeError(
                "skill binding r3 is not available: "
                + ",".join(readiness.reasons)
            )
    if binding.status == "provisioning":
        binding, _ = registry.update_binding(
            SCOPE,
            SKILL_BINDING_ID,
            UpdateSkillBindingRequest(
                expected_version=binding.version,
                from_status="provisioning",
                to_status="active",
            ),
            idempotency_key="r2-4n-skill-binding-activate-r3",
            actor=ACTOR,
            occurred_at=datetime.now(UTC),
        )
    if binding.status != "active" or _readiness_value(binding) != "available":
        raise RuntimeError("skill binding r3 did not become active and available")

    historical_after = registry.get_binding(SCOPE, HISTORICAL_SKILL_BINDING_ID)
    historical_skill_after = registry.get_skill(SKILL_ID, HISTORICAL_SKILL_REVISION)
    if historical_skill_after.content_hash != historical.content_hash:
        raise RuntimeError("Skill r2 was mutated")
    if historical_after.skill.revision != HISTORICAL_SKILL_REVISION:
        raise RuntimeError("SkillBinding r2 skill revision was mutated")

    return {
        "status": "R2_4N_D03_SKILL_PUBLICATION_ROUTE_GATE_ALIGNED",
        "skillRevision": published.revision,
        "skillHash": published.content_hash,
        "skillRoute": dump_ref(published.model_route_ref),
        "skillReleaseGate": dump_ref(published.release_gate_ref),
        "bindingId": binding.binding_id,
        "bindingVersion": binding.version,
        "bindingStatus": binding.status,
        "bindingReadiness": _readiness_value(binding),
        "bindingReasons": list(binding.readiness_reasons),
        "historicalSkillRevision": historical_skill_after.revision,
        "historicalBindingReadiness": _readiness_value(historical_after),
        "canaryBindingCount": _canary_binding_count(),
        "providerBusinessCalls": PROVIDER_BUSINESS_CALL_LIMIT,
        "healthProbes": HEALTH_PROBE_LIMIT,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else inspect()
    except ALIGN_ERRORS as exc:
        result = {
            "status": "blocked",
            "blocker": type(exc).__name__,
            "blockerCode": str(exc),
            "providerBusinessCalls": PROVIDER_BUSINESS_CALL_LIMIT,
            "healthProbes": HEALTH_PROBE_LIMIT,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    ok = result.get("status") in {
        "aligned",
        "drift",
        "R2_4N_D03_SKILL_PUBLICATION_ROUTE_GATE_ALIGNED",
    }
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
