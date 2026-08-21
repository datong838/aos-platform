#!/usr/bin/env python3
"""Cascade Policy/Model/Route/Capacity/Skill onto Provider r7 (domestic).

Default is inspect/dry-run. --apply publishes additive revisions and a new
D03 Binding r4. Never starts AgentRun. Never probes Provider health.
"""
from __future__ import annotations

import argparse
import importlib.util
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
from aos_api.aip_capability_binding_service import AipCapabilityBindingService  # noqa: E402
from aos_api.aip_model_capacity_authority import (  # noqa: E402
    AipModelCapacityAuthorityStore,
    CapacityPoolAuthorityConflict,
    CapacityPoolAuthorityDependencyBlocked,
    CapacityPoolRevisionCreate,
)
from aos_api.aip_model_runtime_contracts import (  # noqa: E402
    ModelRouteCandidate,
    ModelRouteRevision,
    RegisteredModelRevision,
    RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import (  # noqa: E402
    AipModelRuntimeStore,
    ModelRuntimeConflict,
    ModelRuntimeDependencyBlocked,
    ModelRuntimeNotFound,
    canonical_hash,
    evaluation_candidate_ref,
)
from aos_api.aip_network_policy_store import AipNetworkPolicyStore  # noqa: E402
from aos_api.aip_provider_plugin_authority import (  # noqa: E402
    ProviderPluginAuthority,
    ProviderPluginAuthorityError,
)
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore  # noqa: E402
from aos_api.aip_skill_publication_service import AipSkillPublicationService  # noqa: E402
from aos_api.aip_skill_registry import AipSkillRegistry  # noqa: E402
from aos_api.db import connect as db_connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-4y-provider-r7-cascade"
PROVIDER_ID = "agnes-text-qyh-dev"
MODEL_ID = "model-qyh-text-dev"
ROUTE_ID = "route-qyh-text-dev"
POLICY_ID = "policy-qyh-text-dev"
CAPACITY_ID = "capacity-qyh-text-dev"
NETWORK_ID = "network-qyh-text-dev"
EGRESS_ID = "agnes-text-qyh-dev-egress"
PROVIDER_MODEL_ID = "agnes-2.5-flash"
SKILL_ID = "ecommerce.skill.D03"
SOURCE_SKILL_REVISION = 1
HISTORICAL_SKILL_REVISION = 3
TARGET_SKILL_REVISION = 4
SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r4"
HISTORICAL_SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r3"
CAPABILITY_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
ID_FIELDS = {
    "ProviderPluginRevision": "provider_plugin_id",
    "ProviderInstanceRevision": "provider_instance_id",
    "RegisteredModelRevision": "registered_model_id",
    "ModelRouteRevision": "route_id",
    "RuntimePolicyRevision": "policy_id",
    "SkillTemplate": "skill_id",
}
ALIGN_ERRORS = (
    RuntimeError,
    KeyError,
    ValueError,
    TypeError,
    ProviderPluginAuthorityError,
    ModelRuntimeConflict,
    ModelRuntimeDependencyBlocked,
    ModelRuntimeNotFound,
    CapacityPoolAuthorityConflict,
    CapacityPoolAuthorityDependencyBlocked,
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryTransitionBlocked,
)


def load_bootstrap():
    path = Path(__file__).resolve().parent / "bootstrap_r1_runtime_authority.py"
    spec = importlib.util.spec_from_file_location("bootstrap_r1_runtime_authority", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LIVE_MODEL_CASE_IDS = set()
    return module


def exact_ref(kind: str, item: Any, id_attr: str | None = None) -> VersionedAssetRef:
    attr = id_attr or ID_FIELDS[kind]
    return VersionedAssetRef(
        assetType=kind,
        assetId=getattr(item, attr),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def dump_ref(ref: VersionedAssetRef | None) -> dict[str, Any] | None:
    if ref is None:
        return None
    return ref.model_dump(mode="json", by_alias=True)


def rehash_runtime(model: type, payload: dict[str, Any]):
    provisional = model.model_validate({**payload, "contentHash": "0" * 64})
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {name: value for name, value in dumped.items() if name not in META_FIELDS}
    return model.model_validate({**payload, "contentHash": canonical_hash(content)})


def policy_cases() -> list[dict[str, Any]]:
    kinds = ["positive", "boundary", "negative", "tenant"]
    return [
        {
            "caseId": f"align-4y-{index:02d}",
            "kind": kinds[index % len(kinds)],
            "prompt": "capability-alignment-contract",
            "expectedBehavior": "non_empty",
            "routeTaskType": "chat.answer",
            "routeInputModality": "text",
            "routeCapability": "llm",
            "routeExpected": "SELECT",
        }
        for index in range(20)
    ]


def _head(kind: str, asset_id: str) -> dict[str, int]:
    table = f"aip_{kind}_head"
    column = f"{kind}_id"
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            f"SELECT current_revision, version FROM {table} "
            f"WHERE org_id=%s AND project_id=%s AND {column}=%s",
            (*SCOPE.key, asset_id),
        ).fetchone()
    if not row:
        raise RuntimeError(f"{kind} head missing: {asset_id}")
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


def _capacity_head() -> dict[str, int]:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT current_revision, version FROM aip_model_capacity_pool_head "
            "WHERE org_id=%s AND project_id=%s AND pool_id=%s",
            (*SCOPE.key, CAPACITY_ID),
        ).fetchone()
    if not row:
        raise RuntimeError("capacity head missing")
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


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


def _readiness_value(item: Any) -> str | None:
    if item is None:
        return None
    readiness = getattr(item, "readiness", None)
    if readiness is None:
        return None
    return getattr(readiness, "value", str(readiness))


def _canary_binding_count() -> int:
    with db_connect(CANARY_SCOPE) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM aip_skill_binding "
                "WHERE org_id=%s AND project_id=%s AND binding_id=%s",
                (*CANARY_SCOPE.key, SKILL_BINDING_ID),
            ).fetchone()["n"]
        )


def inspect() -> dict[str, Any]:
    store = AipModelRuntimeStore()
    plugin = ProviderPluginAuthority().get(SCOPE, "agnes-text")
    provider_head = _head("provider_instance", PROVIDER_ID)
    model_head = _head("registered_model", MODEL_ID)
    route_head = _head("model_route", ROUTE_ID)
    policy_head = _head("runtime_policy", POLICY_ID)
    capacity_head = _capacity_head()
    network = AipNetworkPolicyStore().get(SCOPE, NETWORK_ID)
    egress = AipRuntimeGuardPolicyStore().get_egress(SCOPE, EGRESS_ID)
    provider = store.get_provider(SCOPE, PROVIDER_ID, provider_head["revision"])
    model = store.get_model(SCOPE, MODEL_ID, model_head["revision"])
    route = store.get_route(SCOPE, ROUTE_ID, route_head["revision"])
    policy = store.get_policy(SCOPE, POLICY_ID, policy_head["revision"])
    capacity = AipModelCapacityAuthorityStore().get(SCOPE, CAPACITY_ID)
    skill = _skill_or_none(TARGET_SKILL_REVISION)
    binding = _binding_or_none(SCOPE, SKILL_BINDING_ID)
    aligned = bool(
        provider.revision == 7
        and plugin.revision == 3
        and plugin.default_models == [PROVIDER_MODEL_ID]
        and str(provider.endpoint_profile.base_url).rstrip("/")
        == "https://api.agnes-ai.cn/v1"
        and network.revision == 3
        and egress.revision == 3
        and policy.network_policy_ref.revision == 3
        and policy.egress_policy_ref.revision == 3
        and model.provider.revision == 7
        and model.provider_model_id == PROVIDER_MODEL_ID
        and route.candidates[0].model.revision == model.revision
        and route.runtime_policy_ref.revision == policy.revision
        and capacity.provider_ref.revision == 7
        and capacity.model_ref.revision == model.revision
        and capacity.route_ref.revision == route.revision
        and skill is not None
        and skill.revision == TARGET_SKILL_REVISION
        and skill.model_route_ref.revision == route.revision
        and skill.runtime_policy_ref.revision == policy.revision
        and binding is not None
        and binding.skill.revision == TARGET_SKILL_REVISION
        and _readiness_value(binding) == "available"
        and binding.status == "active"
    )
    return {
        "status": "aligned" if aligned else "ready",
        "pluginRevision": plugin.revision,
        "provider": dump_ref(exact_ref("ProviderInstanceRevision", provider)),
        "baseUrl": provider.endpoint_profile.base_url,
        "networkRevision": network.revision,
        "egressRevision": egress.revision,
        "policy": {
            **policy_head,
            "networkRevision": policy.network_policy_ref.revision,
            "egressRevision": policy.egress_policy_ref.revision,
        },
        "model": {
            **model_head,
            "providerRevision": model.provider.revision,
            "providerModelId": model.provider_model_id,
        },
        "route": {
            **route_head,
            "modelRevision": route.candidates[0].model.revision,
        },
        "capacity": {
            **capacity_head,
            "providerRevision": capacity.provider_ref.revision,
            "modelRevision": capacity.model_ref.revision,
            "routeRevision": capacity.route_ref.revision,
        },
        "skillRevision": None if skill is None else skill.revision,
        "binding": None
        if binding is None
        else {
            "bindingId": binding.binding_id,
            "skillRevision": binding.skill.revision,
            "status": binding.status,
            "readiness": _readiness_value(binding),
        },
        "canaryBindingCount": _canary_binding_count(),
        "providerBusinessCalls": 0,
        "healthProbes": 0,
    }


def apply() -> dict[str, Any]:
    snapshot = inspect()
    if snapshot["canaryBindingCount"] != 0:
        raise RuntimeError("negative canary already has SkillBinding r4")
    if snapshot["status"] == "aligned":
        return {**snapshot, "status": "R2_4Y_PROVIDER_R7_CASCADE_ALIGNED"}
    boot = load_bootstrap()
    store = AipModelRuntimeStore()
    now = datetime.now(UTC)
    provider_head = _head("provider_instance", PROVIDER_ID)
    provider = store.get_provider(SCOPE, PROVIDER_ID, provider_head["revision"])
    if provider.revision != 7:
        raise RuntimeError(f"expected Provider r7, got r{provider.revision}")
    ProviderPluginAuthority().get(SCOPE, "agnes-text", 3)
    network = AipNetworkPolicyStore().get(SCOPE, NETWORK_ID)
    egress = AipRuntimeGuardPolicyStore().get_egress(SCOPE, EGRESS_ID)
    if network.revision != 3 or egress.revision != 3:
        raise RuntimeError("expected Network r3 and Egress r3")
    provider_ref = exact_ref("ProviderInstanceRevision", provider)
    network_ref = VersionedAssetRef(
        assetType="NetworkPolicyRevision",
        assetId=network.policy_id,
        revision=network.revision,
        contentHash=network.content_hash,
    )
    egress_ref = VersionedAssetRef(
        assetType="EgressPolicyRevision",
        assetId=egress.policy_id,
        revision=egress.revision,
        contentHash=egress.content_hash,
    )

    policy_head = _head("runtime_policy", POLICY_ID)
    policy = store.get_policy(SCOPE, POLICY_ID, policy_head["revision"])
    if (
        policy.network_policy_ref.revision != 3
        or policy.egress_policy_ref.revision != 3
    ):
        policy_payload = policy.model_dump(mode="json", by_alias=True)
        policy_payload.update(
            revision=policy_head["revision"] + 1,
            networkPolicyRef=network_ref.model_dump(mode="json", by_alias=True),
            egressPolicyRef=egress_ref.model_dump(mode="json", by_alias=True),
            createdBy=ACTOR,
            createdAt=now,
        )
        policy_payload.pop("contentHash", None)
        policy = store.publish_policy(
            SCOPE,
            ACTOR,
            "r2-4y-policy-qyh-text-dev-cn-r2",
            rehash_runtime(RuntimePolicyRevision, policy_payload),
            expected_version=policy_head["version"],
        )

    cases = policy_cases()
    dataset = boot._register_goldset(cases)
    model_head = _head("registered_model", MODEL_ID)
    model = store.get_model(SCOPE, MODEL_ID, model_head["revision"])
    if model.provider.revision != 7 or model.provider_model_id != PROVIDER_MODEL_ID:
        model_payload = model.model_dump(mode="json", by_alias=True)
        model_payload.update(
            revision=model_head["revision"] + 1,
            provider=dump_ref(provider_ref),
            providerModelId=PROVIDER_MODEL_ID,
            evalGateRef=boot.PLACEHOLDER_GATE.model_dump(mode="json", by_alias=True),
            createdBy=ACTOR,
            createdAt=now,
        )
        model_payload.pop("contentHash", None)
        model_candidate = rehash_runtime(RegisteredModelRevision, model_payload)
        model_gate = boot._derive_gate(
            target_ref=evaluation_candidate_ref(model_candidate),
            cases=cases,
            dataset=dataset,
            mode="model",
            provider_ref=provider_ref,
            network_ref=network_ref,
        )
        model = store.publish_model(
            SCOPE,
            ACTOR,
            "r2-4y-model-qyh-text-dev-provider-r7",
            rehash_runtime(
                RegisteredModelRevision,
                {
                    **model_payload,
                    "evalGateRef": model_gate.model_dump(mode="json", by_alias=True),
                },
            ),
            expected_version=model_head["version"],
        )

    route_head = _head("model_route", ROUTE_ID)
    route = store.get_route(SCOPE, ROUTE_ID, route_head["revision"])
    policy_ref = exact_ref("RuntimePolicyRevision", policy)
    needs_route = (
        route.candidates[0].model.revision != model.revision
        or route.runtime_policy_ref != policy_ref
    )
    if needs_route:
        route_payload = route.model_dump(mode="json", by_alias=True)
        route_payload.update(
            revision=route_head["revision"] + 1,
            candidates=[
                ModelRouteCandidate(
                    model=exact_ref("RegisteredModelRevision", model)
                ).model_dump(mode="json", by_alias=True)
            ],
            runtimePolicyRef=dump_ref(policy_ref),
            evalGateRef=boot.PLACEHOLDER_GATE.model_dump(mode="json", by_alias=True),
            createdBy=ACTOR,
            createdAt=now,
        )
        route_payload.pop("contentHash", None)
        route_candidate = rehash_runtime(ModelRouteRevision, route_payload)
        route_gate = boot._derive_gate(
            target_ref=evaluation_candidate_ref(route_candidate),
            cases=cases,
            dataset=dataset,
            mode="route",
            provider_ref=provider_ref,
            network_ref=network_ref,
            route_candidate=route_candidate,
        )
        route = store.publish_route(
            SCOPE,
            ACTOR,
            f"r2-4y-route-qyh-text-dev-policy-r{policy.revision}",
            rehash_runtime(
                ModelRouteRevision,
                {
                    **route_payload,
                    "evalGateRef": route_gate.model_dump(mode="json", by_alias=True),
                },
            ),
            expected_version=route_head["version"],
        )

    capacity_head = _capacity_head()
    capacity_current = AipModelCapacityAuthorityStore().get(SCOPE, CAPACITY_ID)
    if (
        capacity_current.provider_ref.revision != 7
        or capacity_current.model_ref.revision != model.revision
        or capacity_current.route_ref.revision != route.revision
    ):
        capacity = AipModelCapacityAuthorityStore().publish(
            SCOPE,
            ACTOR,
            f"r2-4y-capacity-qyh-text-dev-route-r{route.revision}",
            CapacityPoolRevisionCreate(
                poolId=CAPACITY_ID,
                revision=capacity_head["revision"] + 1,
                routeRef=exact_ref("ModelRouteRevision", route),
                modelRef=exact_ref("RegisteredModelRevision", model),
                providerRef=provider_ref,
                maxConcurrency=capacity_current.max_concurrency,
                maxTokenUnits=capacity_current.max_token_units,
                tokenUnitPerReservation=capacity_current.token_unit_per_reservation,
                leaseSeconds=capacity_current.lease_seconds,
                lifecycle="active",
            ),
            expected_version=capacity_head["version"],
        )
    else:
        capacity = capacity_current

    cap_service = AipCapabilityBindingService()
    capability = cap_service.get(SCOPE, CAPABILITY_BINDING_ID)
    cap_deps = capability.dependencies.model_copy(
        update={
            "provider_ref": provider_ref,
            "model_route_ref": exact_ref("ModelRouteRevision", route),
            "runtime_policy_ref": exact_ref("RuntimePolicyRevision", policy),
            "eval_gate_ref": route.eval_gate_ref,
        }
    )
    capability, cap_readiness, _ = cap_service.evaluate(
        SCOPE,
        CAPABILITY_BINDING_ID,
        EvaluateOperationalBindingRequest(
            expectedVersion=capability.version,
            dependencies=cap_deps,
        ),
        idempotency_key="r2-4y-capability-evaluate-v3-after-health",
        actor=ACTOR,
        evaluated_at=datetime.now(UTC),
    )

    registry = AipSkillRegistry()
    source = registry.get_skill(SKILL_ID, SOURCE_SKILL_REVISION)
    historical = registry.get_skill(SKILL_ID, HISTORICAL_SKILL_REVISION)
    historical_binding = registry.get_binding(SCOPE, HISTORICAL_SKILL_BINDING_ID)
    if historical.publication_ref is None or historical.release_gate_ref is None:
        raise RuntimeError("historical Skill r3 missing publication provenance")
    if historical.logic_revision_ref is None:
        raise RuntimeError("historical Skill r3 missing logic ref")
    route_ref = exact_ref("ModelRouteRevision", route)
    policy_ref = exact_ref("RuntimePolicyRevision", policy)
    published, _ = AipSkillPublicationService().publish_evaluated_revision(
        SCOPE,
        PublishEvaluatedSkillRevisionRequest(
            source_skill=exact_ref("SkillTemplate", source, "skill_id"),
            publication_id=historical.publication_ref.revision,
            release_gate_decision_id=historical.release_gate_ref.asset_id,
            model_route_ref=route_ref,
            runtime_policy_ref=policy_ref,
            logic_revision_ref=historical.logic_revision_ref,
            idempotency_key="r2-4y-publish-skill-r4-v2",
        ),
        actor=ACTOR,
        occurred_at=datetime.now(UTC),
    )
    if published.revision != TARGET_SKILL_REVISION:
        raise RuntimeError(f"published skill revision {published.revision} is not r4")

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
            idempotency_key="r2-4y-skill-binding-create-r4",
            actor=ACTOR,
            occurred_at=datetime.now(UTC),
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
        or dump_ref(binding.dependencies.model_route_ref)
        != dump_ref(skill_deps.model_route_ref)
        or dump_ref(binding.dependencies.eval_gate_ref)
        != dump_ref(skill_deps.eval_gate_ref)
    ):
        binding, readiness, _ = registry.evaluate_binding(
            SCOPE,
            SKILL_BINDING_ID,
            EvaluateOperationalBindingRequest(
                expected_version=binding.version,
                dependencies=skill_deps,
            ),
            idempotency_key="r2-4y-skill-binding-evaluate-r4-v2",
            actor=ACTOR,
            evaluated_at=datetime.now(UTC),
        )
        if getattr(readiness.readiness, "value", str(readiness.readiness)) != "available":
            raise RuntimeError(
                "skill binding r4 is not available: " + ",".join(readiness.reasons)
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
            idempotency_key="r2-4y-skill-binding-activate-r4-v2",
            actor=ACTOR,
            occurred_at=datetime.now(UTC),
        )
    if binding.status != "active" or _readiness_value(binding) != "available":
        raise RuntimeError("skill binding r4 did not become active and available")

    return {
        "status": "R2_4Y_PROVIDER_R7_CASCADE_ALIGNED",
        "providerRevision": provider.revision,
        "policyRevision": policy.revision,
        "modelRevision": model.revision,
        "routeRevision": route.revision,
        "capacityRevision": capacity.revision,
        "skillRevision": published.revision,
        "skillHash": published.content_hash,
        "bindingId": binding.binding_id,
        "bindingReadiness": _readiness_value(binding),
        "capabilityReadiness": getattr(
            cap_readiness.readiness, "value", str(cap_readiness.readiness)
        ),
        "canaryBindingCount": _canary_binding_count(),
        "providerBusinessCalls": 0,
        "healthProbes": 0,
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
            "providerBusinessCalls": 0,
            "healthProbes": 0,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    ok = result.get("status") in {"ready", "aligned", "R2_4Y_PROVIDER_R7_CASCADE_ALIGNED"}
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
