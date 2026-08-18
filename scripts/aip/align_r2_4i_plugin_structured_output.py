#!/usr/bin/env python3
"""Align Agnes Text plugin approval with model structured_output.

Default is inspect/dry-run. --apply publishes additive provider/model/route/
capacity revisions and re-evaluates the D03 Binding. It never starts an
AgentRun and never probes Provider health.
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
    EvaluateOperationalBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryConflict  # noqa: E402
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked  # noqa: E402
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
    ProviderInstanceRevision,
    RegisteredModelRevision,
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
from aos_api.aip_skill_registry import AipSkillRegistry  # noqa: E402
from aos_api.db import connect as db_connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-r2-4i-plugin-align"
PROVIDER_ID = "agnes-text-qyh-dev"
MODEL_ID = "model-qyh-text-dev"
ROUTE_ID = "route-qyh-text-dev"
CAPACITY_ID = "capacity-qyh-text-dev"
CAPABILITY_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"
SKILL_BINDING_ID = "ecommerce.data_advisor.skill.D03.r2"
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
ID_FIELDS = {
    "ProviderPluginRevision": "provider_plugin_id",
    "ProviderInstanceRevision": "provider_instance_id",
    "RegisteredModelRevision": "registered_model_id",
    "ModelRouteRevision": "route_id",
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


def exact_ref(kind: str, item: Any) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind,
        assetId=getattr(item, ID_FIELDS[kind]),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def dump_ref(kind: str, item: Any) -> dict[str, Any]:
    return exact_ref(kind, item).model_dump(mode="json", by_alias=True)


def rehash_runtime(model: type, payload: dict[str, Any]):
    provisional = model.model_validate({**payload, "contentHash": "0" * 64})
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {name: value for name, value in dumped.items() if name not in META_FIELDS}
    return model.model_validate({**payload, "contentHash": canonical_hash(content)})


def policy_cases() -> list[dict[str, Any]]:
    kinds = ["positive", "boundary", "negative", "tenant"]
    return [
        {
            "caseId": f"align-{index:02d}",
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


def inspect() -> dict[str, Any]:
    plugin = ProviderPluginAuthority().get(SCOPE, "agnes-text")
    store = AipModelRuntimeStore()
    provider_head = _head("provider_instance", PROVIDER_ID)
    model_head = _head("registered_model", MODEL_ID)
    route_head = _head("model_route", ROUTE_ID)
    capacity_head = _capacity_head()
    provider = store.get_provider(SCOPE, PROVIDER_ID, provider_head["revision"])
    model = store.get_model(SCOPE, MODEL_ID, model_head["revision"])
    route = store.get_route(SCOPE, ROUTE_ID, route_head["revision"])
    capacity = AipModelCapacityAuthorityStore().get(SCOPE, CAPACITY_ID)
    capability = AipCapabilityBindingService().get(SCOPE, CAPABILITY_BINDING_ID)
    skill = AipSkillRegistry().get_binding(SCOPE, SKILL_BINDING_ID)
    approved = list(plugin.approved_capabilities)
    mismatch = sorted(set(model.capabilities) - set(approved))
    plugin_ready = plugin.revision == 2 and "structured_output" in approved
    cascade_pending = bool(
        provider.plugin_ref.revision != plugin.revision
        or provider.plugin_ref.content_hash != plugin.content_hash
        or mismatch
    )
    return {
        "status": "ready" if plugin_ready else "blocked",
        "plugin": {
            "revision": plugin.revision,
            "contentHash": plugin.content_hash,
            "approvedCapabilities": approved,
        },
        "providerHead": provider_head,
        "modelHead": model_head,
        "routeHead": route_head,
        "capacityHead": capacity_head,
        "providerPluginRef": provider.plugin_ref.model_dump(mode="json", by_alias=True),
        "modelCapabilities": list(model.capabilities),
        "modelProviderRevision": model.provider.revision,
        "routeModelRevision": route.candidates[0].model.revision,
        "capacityProviderRevision": capacity.provider_ref.revision,
        "capacityModelRevision": capacity.model_ref.revision,
        "capacityRouteRevision": capacity.route_ref.revision,
        "capabilityVersion": capability.version,
        "skillVersion": skill.version,
        "mismatch": mismatch,
        "cascadePending": cascade_pending,
        "providerBusinessCalls": 0,
        "healthProbes": 0,
    }


def apply() -> dict[str, Any]:
    snapshot = inspect()
    if snapshot["status"] != "ready":
        raise RuntimeError("plugin r2 missing structured_output")
    boot = load_bootstrap()
    plugin = ProviderPluginAuthority().get(SCOPE, "agnes-text", 2)
    store = AipModelRuntimeStore()
    provider_head = snapshot["providerHead"]
    model_head = snapshot["modelHead"]
    route_head = snapshot["routeHead"]
    capacity_head = snapshot["capacityHead"]

    provider_current = store.get_provider(SCOPE, PROVIDER_ID, provider_head["revision"])
    provider_payload = provider_current.model_dump(mode="json", by_alias=True)
    provider_payload.update(
        revision=provider_head["revision"] + 1,
        pluginRef=dump_ref("ProviderPluginRevision", plugin),
        createdBy=ACTOR,
        createdAt=datetime.now(UTC),
    )
    provider_payload.pop("contentHash", None)
    provider = store.publish_provider(
        SCOPE,
        ACTOR,
        "r2-4i-provider-agnes-text-qyh-dev-plugin-r2",
        rehash_runtime(ProviderInstanceRevision, provider_payload),
        expected_version=provider_head["version"],
    )

    cases = policy_cases()
    dataset = boot._register_goldset(cases)
    network = AipNetworkPolicyStore().get(SCOPE, "network-qyh-text-dev", 1)
    network_ref = VersionedAssetRef(
        assetType="NetworkPolicyRevision",
        assetId=network.policy_id,
        revision=network.revision,
        contentHash=network.content_hash,
    )
    provider_ref = exact_ref("ProviderInstanceRevision", provider)

    model_current = store.get_model(SCOPE, MODEL_ID, model_head["revision"])
    model_payload = model_current.model_dump(mode="json", by_alias=True)
    model_payload.update(
        revision=model_head["revision"] + 1,
        provider=dump_ref("ProviderInstanceRevision", provider),
        evalGateRef=boot.PLACEHOLDER_GATE.model_dump(mode="json", by_alias=True),
        createdBy=ACTOR,
        createdAt=datetime.now(UTC),
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
        "r2-4i-model-qyh-text-dev-provider-cascade",
        rehash_runtime(
            RegisteredModelRevision,
            {**model_payload, "evalGateRef": model_gate.model_dump(mode="json", by_alias=True)},
        ),
        expected_version=model_head["version"],
    )

    route_current = store.get_route(SCOPE, ROUTE_ID, route_head["revision"])
    route_payload = route_current.model_dump(mode="json", by_alias=True)
    route_payload.update(
        revision=route_head["revision"] + 1,
        candidates=[
            ModelRouteCandidate(
                model=exact_ref("RegisteredModelRevision", model)
            ).model_dump(mode="json", by_alias=True)
        ],
        evalGateRef=boot.PLACEHOLDER_GATE.model_dump(mode="json", by_alias=True),
        createdBy=ACTOR,
        createdAt=datetime.now(UTC),
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
        "r2-4i-route-qyh-text-dev-model-cascade",
        rehash_runtime(
            ModelRouteRevision,
            {**route_payload, "evalGateRef": route_gate.model_dump(mode="json", by_alias=True)},
        ),
        expected_version=route_head["version"],
    )

    capacity_current = AipModelCapacityAuthorityStore().get(SCOPE, CAPACITY_ID)
    capacity = AipModelCapacityAuthorityStore().publish(
        SCOPE,
        ACTOR,
        "r2-4i-capacity-qyh-text-dev-cascade",
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

    cap_service = AipCapabilityBindingService()
    capability = cap_service.get(SCOPE, CAPABILITY_BINDING_ID)
    cap_deps = capability.dependencies.model_copy(
        update={
            "provider_ref": provider_ref,
            "model_route_ref": exact_ref("ModelRouteRevision", route),
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
        idempotency_key="r2-4i-capability-evaluate",
        actor=ACTOR,
        evaluated_at=datetime.now(UTC),
    )

    skill_service = AipSkillRegistry()
    binding = skill_service.get_binding(SCOPE, SKILL_BINDING_ID)
    skill_deps = binding.dependencies.model_copy(
        update={
            "model_route_ref": exact_ref("ModelRouteRevision", route),
            "eval_gate_ref": route.eval_gate_ref,
        }
    )
    binding, skill_readiness, _ = skill_service.evaluate_binding(
        SCOPE,
        SKILL_BINDING_ID,
        EvaluateOperationalBindingRequest(
            expectedVersion=binding.version,
            dependencies=skill_deps,
        ),
        idempotency_key="r2-4i-skill-evaluate",
        actor=ACTOR,
        evaluated_at=datetime.now(UTC),
    )
    return {
        "status": "R2_4I_PLUGIN_STRUCTURED_OUTPUT_ALIGNED",
        "pluginRevision": plugin.revision,
        "pluginHash": plugin.content_hash,
        "providerRevision": provider.revision,
        "modelRevision": model.revision,
        "routeRevision": route.revision,
        "capacityRevision": capacity.revision,
        "capabilityVersion": capability.version,
        "skillVersion": binding.version,
        "capabilityReadiness": getattr(
            cap_readiness.readiness, "value", str(cap_readiness.readiness)
        ),
        "capabilityReasons": list(cap_readiness.reasons),
        "skillReadiness": getattr(
            skill_readiness.readiness, "value", str(skill_readiness.readiness)
        ),
        "skillReasons": list(skill_readiness.reasons),
        "secretPayloadReads": 0,
        "providerBusinessCalls": 0,
        "healthProbes": 0,
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
    return 0 if result.get("status") in {
        "ready",
        "R2_4I_PLUGIN_STRUCTURED_OUTPUT_ALIGNED",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
