#!/usr/bin/env python3
"""Compose the one approved V01 runnable binding chain without calling Provider.

The default mode is a read-only inspection. ``--apply`` is fail-closed unless
the existing R1 route is READY at the decision time; it copies only the opaque
Secret reference already held by Provider authority and never resolves it.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any, NamedTuple

from aos_api.aip_agent_control_contracts import ActivateAgentInstanceRequest
from aos_api.aip_agent_instance_activation_service import (
    AipAgentInstanceActivationService,
)
from aos_api.aip_agent_registry_contracts import (
    BindingHealth,
    CapabilityBindingRequest,
    CapabilityReadiness,
    CreateCapabilityBindingRequest,
    CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest,
    OperationalBindingDependencies,
    UpdateCapabilityBindingRequest,
    UpdateSkillBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_binding_api_contracts import CapabilityBindingPreviewRequest
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-v01-binding-bootstrap"
APPROVAL_REF = "46-R2-V01-VIDEO-DRAFT"
REQUIRED_ALEMBIC_HEAD = "aip10_006"

CAPABILITY_ID = "video.generate"
CAPABILITY_REVISION = 2
SKILL_ID = "ecommerce.skill.V01"
SKILL_REVISION = 2
INSTANCE_ID = "ecommerce.content_officer.default"
ROUTE_ID = "route-qyh-video-dev"
EVAL_SUITE_ID = "ecommerce.skill.V01.contract.v1"
CAPABILITY_BINDING_ID = "ecommerce.content_officer.video.generate.r2"
SKILL_BINDING_ID = "ecommerce.content_officer.skill.V01.r2"


class CompositionBlocked(RuntimeError):
    def __init__(self, code: str, reasons: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reasons = sorted(set(reasons or []))


class ExactComposition(NamedTuple):
    capability: Any
    skill: Any
    instance: Any
    provider: Any
    route: Any
    policy: Any
    eval_contract_ref: VersionedAssetRef
    license_evidence_ref: ResourceRef
    dependencies: OperationalBindingDependencies


def exact_ref(asset_type: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=str(getattr(item, id_attr)),
        revision=int(item.revision),
        content_hash=str(item.content_hash),
    )


def compact_revision(ref: VersionedAssetRef) -> str:
    value = f"{ref.asset_id}@{ref.revision}#{ref.content_hash}"
    if len(value) > 120:
        raise CompositionBlocked("EXACT_REVISION_REF_TOO_LONG")
    return value


def runtime_blocker_code(reasons: list[str]) -> str:
    return (
        "PROVIDER_HEALTH_REFRESH_REQUIRED"
        if any("HEALTH" in reason.upper() for reason in reasons)
        else "MODEL_RUNTIME_NOT_READY"
    )


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "approvalRef": APPROVAL_REF,
        "order": [
            "CapabilityBinding create/evaluate/activate",
            "AgentInstance activate",
            "SkillBinding create/evaluate/activate",
        ],
        "providerCalls": 0,
        "secretPayloadReads": 0,
        "forbiddenSideEffects": ["AgentRun", "Provider call", "migration"],
    }


def _require_schema_head() -> None:
    with db_connect(SCOPE) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    current = str(row["version_num"]) if row else ""
    if current != REQUIRED_ALEMBIC_HEAD:
        raise CompositionBlocked(
            "SCHEMA_HEAD_MISMATCH", [f"expected={REQUIRED_ALEMBIC_HEAD}", f"actual={current}"]
        )


def _contract_and_evidence_refs() -> tuple[VersionedAssetRef, ResourceRef]:
    subject = json.dumps(
        [{"resourceType": "SkillTemplate", "resourceId": SKILL_ID}],
        ensure_ascii=False,
    )
    with db_connect(SCOPE) as conn:
        contract = conn.execute(
            """SELECT contract_id,revision,content_hash FROM aip_eval_contract_revision
               WHERE org_id=%s AND project_id=%s AND lifecycle='frozen'
                 AND suite_ref->>'resourceId'=%s
               ORDER BY revision DESC LIMIT 1""",
            (*SCOPE.key, EVAL_SUITE_ID),
        ).fetchone()
        bundle = conn.execute(
            """SELECT bundle_id,revision,content_hash FROM aip_evidence_bundle_revision
               WHERE org_id=%s AND project_id=%s AND lifecycle='frozen'
                 AND license_summary IS NOT NULL
                 AND subject_refs @> %s::jsonb
               ORDER BY revision DESC LIMIT 1""",
            (*SCOPE.key, subject),
        ).fetchone()
    if contract is None:
        raise CompositionBlocked("EVAL_CONTRACT_MISSING")
    if bundle is None:
        raise CompositionBlocked("LICENSE_EVIDENCE_MISSING")
    return (
        VersionedAssetRef(
            asset_type="EvalContractRevision",
            asset_id=contract["contract_id"],
            revision=int(contract["revision"]),
            content_hash=contract["content_hash"],
        ),
        ResourceRef(
            resource_type="EvidenceBundleRevision",
            resource_id=bundle["bundle_id"],
            revision=str(bundle["revision"]),
            authority="aip-production-contract",
        ),
    )


def load_exact_composition(*, evaluated_at: datetime) -> ExactComposition:
    _require_schema_head()
    capability = AipCapabilityRegistry().get(CAPABILITY_ID, CAPABILITY_REVISION)
    skill = AipSkillRegistry().get_skill(SKILL_ID, SKILL_REVISION)
    instance = AipAgentRegistryStore().get_instance(SCOPE, INSTANCE_ID)
    runtime = AipModelRuntimeStore()
    route = runtime.get_route(
        SCOPE, skill.model_route_ref.asset_id, skill.model_route_ref.revision
    )
    policy = runtime.get_policy(
        SCOPE, skill.runtime_policy_ref.asset_id, skill.runtime_policy_ref.revision
    )
    resolution = AipModelRuntimeResolver(runtime).resolve(
        SCOPE, ROUTE_ID, now=evaluated_at
    )
    if resolution.readiness is not ModelRuntimeReadiness.READY:
        raise CompositionBlocked(
            runtime_blocker_code(list(resolution.blocker_codes)),
            list(resolution.blocker_codes),
        )
    if resolution.selected_provider is None:
        raise CompositionBlocked("PROVIDER_REF_MISSING")
    provider = runtime.get_provider(
        SCOPE,
        resolution.selected_provider.asset_id,
        resolution.selected_provider.revision,
    )
    eval_contract_ref, license_evidence_ref = _contract_and_evidence_refs()
    dependencies = OperationalBindingDependencies(
        provider_ref=resolution.selected_provider,
        model_route_ref=resolution.route,
        runtime_policy_ref=resolution.policy,
        eval_gate_ref=route.eval_gate_ref,
        eval_contract_ref=eval_contract_ref,
        license_evidence_refs=[license_evidence_ref],
        data_dependency_refs=list(capability.required_data_refs),
        tool_dependency_refs=list(capability.required_tool_refs),
        budget_policy_ref=policy.budget_policy_ref,
        allow_degraded=False,
    )
    return ExactComposition(
        capability=capability,
        skill=skill,
        instance=instance,
        provider=provider,
        route=route,
        policy=policy,
        eval_contract_ref=eval_contract_ref,
        license_evidence_ref=license_evidence_ref,
        dependencies=dependencies,
    )


def _counts(scope: TenantScope) -> dict[str, int]:
    with db_connect(scope) as conn:
        return {
            "capabilityBinding": int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM aip_capability_binding WHERE org_id=%s AND project_id=%s AND binding_id=%s",
                    (*scope.key, CAPABILITY_BINDING_ID),
                ).fetchone()["n"]
            ),
            "skillBinding": int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM aip_skill_binding WHERE org_id=%s AND project_id=%s AND binding_id=%s",
                    (*scope.key, SKILL_BINDING_ID),
                ).fetchone()["n"]
            ),
            "agentRun": int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM aip_agent_run WHERE org_id=%s AND project_id=%s",
                    scope.key,
                ).fetchone()["n"]
            ),
        }


def inspect(*, now: datetime | None = None) -> dict[str, Any]:
    decision_at = now or datetime.now(UTC)
    before = _counts(SCOPE)
    try:
        composition = load_exact_composition(evaluated_at=decision_at)
    except CompositionBlocked as exc:
        return {
            **build_plan(),
            "status": "blocked",
            "blockerCode": exc.code,
            "blockerReasons": exc.reasons,
            "sideEffectCounts": before,
        }
    preview = AipCapabilityBindingService().preview(
        SCOPE,
        request=CapabilityBindingPreviewRequest(
            capability=exact_ref(
                "CapabilityRevision", composition.capability, "capability_id"
            ),
            dependencies=composition.dependencies,
        ),
        evaluated_at=decision_at,
    )
    return {
        **build_plan(),
        "status": "ready" if preview.readiness is CapabilityReadiness.AVAILABLE else "blocked",
        "blockerCode": None if preview.readiness is CapabilityReadiness.AVAILABLE else "CAPABILITY_BINDING_NOT_READY",
        "blockerReasons": preview.reasons,
        "dependencySnapshotHash": preview.dependency_snapshot_hash,
        "sideEffectCounts": before,
    }


def skill_binding_dependencies(
    composition: ExactComposition | Any,
) -> OperationalBindingDependencies:
    """Use the Skill publication gate, never the ModelRoute evaluation gate."""
    skill = composition.skill
    if (
        skill.release_gate_ref is None
        or skill.model_route_ref is None
        or skill.runtime_policy_ref is None
    ):
        raise CompositionBlocked("SKILL_PUBLICATION_PROVENANCE_MISSING")
    if (
        skill.model_route_ref != composition.dependencies.model_route_ref
        or skill.runtime_policy_ref != composition.dependencies.runtime_policy_ref
    ):
        raise CompositionBlocked("SKILL_PUBLICATION_RUNTIME_REF_DRIFT")
    return OperationalBindingDependencies(
        model_route_ref=skill.model_route_ref,
        runtime_policy_ref=skill.runtime_policy_ref,
        eval_gate_ref=skill.release_gate_ref,
        budget_policy_ref=composition.dependencies.budget_policy_ref,
    )


def _skill_readiness_reusable(
    binding: Any,
    dependencies: OperationalBindingDependencies,
    decision_at: datetime,
) -> bool:
    return bool(
        binding.readiness is CapabilityReadiness.AVAILABLE
        and binding.dependencies == dependencies
        and binding.dependency_snapshot_hash
        and binding.readiness_expires_at
        and binding.readiness_expires_at > decision_at
    )


def ensure_skill_binding_active(
    *,
    service: Any,
    binding: Any,
    dependencies: OperationalBindingDependencies,
    decision_at: datetime,
) -> Any:
    """Resume the approved SkillBinding composition without duplicate writes."""
    if binding.status == "active":
        if not _skill_readiness_reusable(binding, dependencies, decision_at):
            raise CompositionBlocked("ACTIVE_SKILL_BINDING_READINESS_STALE")
        return binding
    if binding.status != "provisioning":
        raise CompositionBlocked(
            "SKILL_BINDING_LIFECYCLE_NOT_RESUMABLE", [str(binding.status)]
        )
    if not _skill_readiness_reusable(binding, dependencies, decision_at):
        binding, readiness, _ = service.evaluate_binding(
            SCOPE,
            binding.binding_id,
            EvaluateOperationalBindingRequest(
                expected_version=binding.version,
                dependencies=dependencies,
            ),
            idempotency_key=(
                f"{APPROVAL_REF}-skill-binding-evaluate-skill-gate-v1"
            ),
            actor=ACTOR,
            evaluated_at=decision_at,
        )
        if readiness.readiness is not CapabilityReadiness.AVAILABLE:
            raise CompositionBlocked("SKILL_BINDING_NOT_READY", readiness.reasons)
    binding, _ = service.update_binding(
        SCOPE,
        binding.binding_id,
        UpdateSkillBindingRequest(
            expected_version=binding.version,
            from_status="provisioning",
            to_status="active",
        ),
        idempotency_key=f"{APPROVAL_REF}-skill-binding-activate-skill-gate-v1",
        actor=ACTOR,
        occurred_at=decision_at,
    )
    return binding


def ensure_capability_binding_active(
    *,
    service: Any,
    binding: Any,
    readiness: Any,
    decision_at: datetime,
) -> Any:
    """Do not replay the timestamped activation command after it succeeded."""
    if binding.status == "active":
        if (
            readiness.readiness is not CapabilityReadiness.AVAILABLE
            or readiness.expires_at <= decision_at
        ):
            raise CompositionBlocked("ACTIVE_CAPABILITY_BINDING_READINESS_STALE")
        return binding
    if binding.status != "provisioning":
        raise CompositionBlocked(
            "CAPABILITY_BINDING_LIFECYCLE_NOT_RESUMABLE", [str(binding.status)]
        )
    binding, _ = service.update(
        SCOPE,
        CAPABILITY_BINDING_ID,
        UpdateCapabilityBindingRequest(
            expected_version=binding.version,
            from_status="provisioning",
            to_status="active",
            health=BindingHealth.HEALTHY,
            observed_at=decision_at,
        ),
        idempotency_key=f"{APPROVAL_REF}-capability-binding-activate",
        actor=ACTOR,
    )
    return binding


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    decision_at = now or datetime.now(UTC)
    before = _counts(SCOPE)
    canary_before = _counts(CANARY_SCOPE)
    if any(canary_before.values()):
        raise CompositionBlocked("NEGATIVE_CANARY_NOT_EMPTY")
    composition = load_exact_composition(evaluated_at=decision_at)
    capability_ref = exact_ref(
        "CapabilityRevision", composition.capability, "capability_id"
    )
    capability_service = AipCapabilityBindingService()
    preview = capability_service.preview(
        SCOPE,
        request=CapabilityBindingPreviewRequest(
            capability=capability_ref,
            dependencies=composition.dependencies,
        ),
        evaluated_at=decision_at,
    )
    if preview.readiness is not CapabilityReadiness.AVAILABLE:
        raise CompositionBlocked("CAPABILITY_BINDING_NOT_READY", preview.reasons)

    capability_binding, _ = capability_service.create(
        SCOPE,
        CreateCapabilityBindingRequest(
            binding_id=CAPABILITY_BINDING_ID,
            binding=CapabilityBindingRequest(
                capability=capability_ref,
                secret_ref=composition.provider.secret_ref,
                network_policy_revision=compact_revision(
                    composition.policy.network_policy_ref
                ),
                quota_policy_revision=compact_revision(
                    composition.policy.quota_policy_ref
                ),
                timeout_ms=composition.policy.deadline_ms,
                max_concurrency=1,
            ),
        ),
        idempotency_key=f"{APPROVAL_REF}-capability-binding-create",
        actor=ACTOR,
        occurred_at=decision_at,
    )
    capability_binding, readiness, _ = capability_service.evaluate(
        SCOPE,
        CAPABILITY_BINDING_ID,
        EvaluateOperationalBindingRequest(
            expected_version=1,
            dependencies=composition.dependencies,
            expected_dependency_snapshot_hash=preview.dependency_snapshot_hash,
        ),
        idempotency_key=f"{APPROVAL_REF}-capability-binding-evaluate",
        actor=ACTOR,
        evaluated_at=decision_at,
    )
    capability_binding = ensure_capability_binding_active(
        service=capability_service,
        binding=capability_binding,
        readiness=readiness,
        decision_at=decision_at,
    )
    if composition.instance.status.value == "active":
        instance = composition.instance
    else:
        instance, _ = AipAgentInstanceActivationService().activate(
            SCOPE,
            INSTANCE_ID,
            ActivateAgentInstanceRequest(
                expected_version=composition.instance.version,
                capability_binding_ids=[CAPABILITY_BINDING_ID],
            ),
            idempotency_key=f"{APPROVAL_REF}-instance-activate",
            actor=ACTOR,
            occurred_at=decision_at,
        )
    skill_ref = exact_ref("SkillTemplate", composition.skill, "skill_id")
    skill_service = AipSkillRegistry()
    skill_binding, _ = skill_service.create_binding(
        SCOPE,
        CreateSkillBindingRequest(
            binding_id=SKILL_BINDING_ID,
            instance_id=INSTANCE_ID,
            skill=skill_ref,
            capability_binding_ids=[CAPABILITY_BINDING_ID],
            budget_policy_ref=composition.policy.budget_policy_ref,
        ),
        idempotency_key=f"{APPROVAL_REF}-skill-binding-create",
        actor=ACTOR,
        occurred_at=decision_at,
    )
    skill_binding = ensure_skill_binding_active(
        service=skill_service,
        binding=skill_binding,
        dependencies=skill_binding_dependencies(composition),
        decision_at=decision_at,
    )
    canary_after = _counts(CANARY_SCOPE)
    if canary_after != canary_before:
        raise CompositionBlocked("NEGATIVE_CANARY_CHANGED")
    return {
        "status": "V01_BINDING_COMPOSITION_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "capabilityBinding": {
            "bindingId": capability_binding.binding_id,
            "status": capability_binding.status,
            "readiness": readiness.readiness.value,
        },
        "instance": {"instanceId": instance.instance_id, "status": instance.status.value},
        "skillBinding": {
            "bindingId": skill_binding.binding_id,
            "status": skill_binding.status,
            "readiness": skill_binding.readiness.value,
        },
        "beforeCounts": before,
        "afterCounts": _counts(SCOPE),
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else inspect()
    except CompositionBlocked as exc:
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
