from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_agent_registry_contracts import (
    CapabilityBindingRequest,
    CapabilityReadiness,
    CreateCapabilityBindingRequest,
    EvaluateOperationalBindingRequest,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    PublishCapabilityRevisionRequest,
    UpdateCapabilityBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_model_runtime_contracts import ModelRouteResolution
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 15, 2, tzinfo=UTC)
HASHES = {
    name: char * 64
    for name, char in zip("cap route provider policy gate eval budget".split(), "1234567")
}


def ref(kind: str, asset_id: str, content_hash: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind, asset_id=asset_id, revision=1, content_hash=content_hash
    )


def dependencies() -> OperationalBindingDependencies:
    return OperationalBindingDependencies(
        provider_ref=ref("ProviderInstanceRevision", "provider-1", HASHES["provider"]),
        model_route_ref=ref("ModelRouteRevision", "route-1", HASHES["route"]),
        runtime_policy_ref=ref("RuntimePolicyRevision", "policy-1", HASHES["policy"]),
        eval_gate_ref=ref("EvalGateDecision", "gate-1", HASHES["gate"]),
        eval_contract_ref=ref("EvalContractRevision", "eval-1", HASHES["eval"]),
        license_evidence_refs=[
            ResourceRef(
                resource_type="EvidenceBundleRevision",
                resource_id="license-1",
                revision="1",
                authority="aip-production-contract",
            )
        ],
        budget_policy_ref=ref("BudgetPolicyRevision", "budget-1", HASHES["budget"]),
    )


class Authority:
    def __init__(self, *, gate=True, contract=True, license=True, assets=True):
        self.gate = gate
        self.contract = contract
        self.license = license
        self.assets = assets

    def capability(self, _ref):
        return {
            "lifecycle": "published",
            "content_hash": HASHES["cap"],
            "risk_level": "low",
            "required_data_refs": [],
            "required_tool_refs": [],
        }

    def eval_gate_passed(self, _scope, _ref):
        return self.gate

    def eval_contract_frozen(self, _scope, _ref):
        return self.contract

    def license_evidence_available(self, _scope, _refs):
        return self.license

    def exact_assets_available(self, _scope, _refs):
        return self.assets


class Resolver:
    def resolve(self, scope, _route_id, *, now):
        deps = dependencies()
        return ModelRouteResolution(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            route=deps.model_route_ref,
            policy=deps.runtime_policy_ref,
            readiness="ready",
            selectedModel=ref("RegisteredModelRevision", "model-1", "1" * 64),
            selectedProvider=deps.provider_ref,
            selectedPriceSnapshot=ref("ModelPriceSnapshotRevision", "price-1", "2" * 64),
            resolvedAt=now,
        )


class Policy:
    content_hash = HASHES["policy"]
    budget_policy_ref = dependencies().budget_policy_ref


class Route:
    content_hash = HASHES["route"]
    eval_gate_ref = dependencies().eval_gate_ref


class ModelStore:
    def get_route(self, *_args):
        return Route()

    def get_policy(self, *_args):
        return Policy()


class PersistedReadiness:
    def evaluate_capability(self, _scope, capability, deps, *, evaluated_at):
        return OperationalBindingReadiness(
            readiness="available",
            reasons=[],
            dependencies=deps,
            dependency_snapshot_hash=AipBindingReadinessService.snapshot_hash(capability, deps),
            evaluated_at=evaluated_at,
            expires_at=evaluated_at + timedelta(minutes=15),
        )


def test_exact_dependencies_produce_available_deterministic_snapshot():
    service = AipBindingReadinessService(
        authority=Authority(), model_resolver=Resolver(), model_store=ModelStore()
    )
    capability = ref("CapabilityRevision", "wiki.search", HASHES["cap"])
    first = service.evaluate_capability(PRIMARY, capability, dependencies(), evaluated_at=NOW)
    second = service.evaluate_capability(PRIMARY, capability, dependencies(), evaluated_at=NOW)
    assert first.readiness is CapabilityReadiness.AVAILABLE
    assert first.reasons == []
    assert first.dependency_snapshot_hash == second.dependency_snapshot_hash
    assert first.expires_at == NOW + timedelta(minutes=15)


def test_dependency_snapshot_hash_is_insensitive_to_set_like_ref_order():
    capability = ref("CapabilityRevision", "wiki.search", HASHES["cap"])
    first = dependencies()
    first.license_evidence_refs.append(
        ResourceRef(
            resource_type="EvidenceBundleRevision",
            resource_id="license-2",
            revision="1",
            authority="aip-production-contract",
        )
    )
    second = first.model_copy(
        update={"license_evidence_refs": list(reversed(first.license_evidence_refs))}
    )
    assert AipBindingReadinessService.snapshot_hash(
        capability, first
    ) == AipBindingReadinessService.snapshot_hash(capability, second)


def test_missing_exact_dependencies_fail_closed_with_stable_ordered_reasons():
    service = AipBindingReadinessService(
        authority=Authority(gate=False, contract=False, license=False),
        model_resolver=Resolver(),
        model_store=ModelStore(),
    )
    result = service.evaluate_capability(
        PRIMARY,
        ref("CapabilityRevision", "wiki.search", HASHES["cap"]),
        OperationalBindingDependencies(),
        evaluated_at=NOW,
    )
    assert result.readiness is CapabilityReadiness.BLOCKED
    assert result.reasons == [
        "BUDGET_POLICY_MISSING",
        "EVAL_CONTRACT_REF_MISSING",
        "EVAL_GATE_REF_MISSING",
        "LICENSE_EVIDENCE_MISSING",
        "MODEL_ROUTE_REF_MISSING",
        "PROVIDER_REF_MISSING",
        "RUNTIME_POLICY_REF_MISSING",
    ]


def _publish_and_create(service: AipCapabilityBindingService, suffix: str):
    capability_id = f"bind2.capability.{suffix}"
    binding_id = f"bind2-binding-{suffix}"
    AipCapabilityRegistry().publish(
        PublishCapabilityRevisionRequest(
            capability_id=capability_id,
            revision=1,
            display_name="BIND-2 test capability",
            lifecycle="published",
            input_schema_ref=ref("SchemaRevision", "input", "3" * 64),
            output_schema_ref=ref("SchemaRevision", "output", "4" * 64),
            risk_level="low",
            memory_policy_ref=ref("MemoryPolicy", "memory", "5" * 64),
            handoff_policy_ref=ref("HandoffPolicy", "handoff", "6" * 64),
            effect_review_schema_ref=ref("SchemaRevision", "effect", "7" * 64),
            license_policy_ref=ref("LicensePolicy", "license", "8" * 64),
            readiness_policy_ref=ref("ReadinessPolicy", "readiness", "9" * 64),
            readiness="available",
            source_ref=ResourceRef(
                resource_type="SolutionPack", resource_id="bind2", revision="1", authority="aip6"
            ),
            source_license="internal-authorized",
            content_hash=HASHES["cap"],
        ),
        actor="pytest",
    )
    binding, _ = service.create(
        PRIMARY,
        CreateCapabilityBindingRequest(
            binding_id=binding_id,
            binding=CapabilityBindingRequest(
                capability=ref("CapabilityRevision", capability_id, HASHES["cap"]),
                secret_ref="vault://pytest/bind2",
                network_policy_revision="network-1",
                quota_policy_revision="quota-1",
                timeout_ms=1000,
                max_concurrency=1,
            ),
        ),
        idempotency_key=f"create-{suffix}",
        actor="pytest",
        occurred_at=NOW,
    )
    return binding


def test_evaluation_is_tenant_scoped_cas_idempotent_and_required_for_activation():
    suffix = uuid.uuid4().hex[:12]
    evaluation_time = datetime.now(UTC)
    service = AipCapabilityBindingService(readiness_service=PersistedReadiness())
    created = _publish_and_create(service, suffix)
    request = EvaluateOperationalBindingRequest(
        expected_version=1, dependencies=dependencies()
    )
    evaluated, result, receipt = service.evaluate(
        PRIMARY,
        created.binding_id,
        request,
        idempotency_key=f"evaluate-{suffix}",
        actor="pytest",
        evaluated_at=evaluation_time,
    )
    assert evaluated.version == 2
    assert evaluated.operational_readiness is CapabilityReadiness.AVAILABLE
    assert result.dependency_snapshot_hash == evaluated.dependency_snapshot_hash
    assert receipt.operation == "capability_binding.evaluate"
    replay, _, replay_receipt = service.evaluate(
        PRIMARY,
        created.binding_id,
        request,
        idempotency_key=f"evaluate-{suffix}",
        actor="pytest",
        evaluated_at=evaluation_time,
    )
    assert replay.version == 2 and replay_receipt.receipt_id == receipt.receipt_id
    with pytest.raises(AipAgentRegistryNotFound):
        service.get(CANARY, created.binding_id)
    with pytest.raises(AipAgentRegistryConflict):
        service.evaluate(
            PRIMARY,
            created.binding_id,
            EvaluateOperationalBindingRequest(
                expected_version=1,
                dependencies=dependencies(),
                expected_dependency_snapshot_hash="0" * 64,
            ),
            idempotency_key=f"drift-{suffix}",
            actor="pytest",
            evaluated_at=evaluation_time,
        )
    active, _ = service.update(
        PRIMARY,
        created.binding_id,
        UpdateCapabilityBindingRequest(
            expected_version=2,
            from_status="provisioning",
            to_status="active",
            health="healthy",
            observed_at=evaluation_time,
        ),
        idempotency_key=f"activate-{suffix}",
        actor="pytest",
    )
    assert active.status == "active" and active.version == 3


def test_expired_operational_snapshot_blocks_activation():
    suffix = uuid.uuid4().hex[:12]
    evaluation_time = datetime.now(UTC) - timedelta(minutes=20)
    service = AipCapabilityBindingService(readiness_service=PersistedReadiness())
    created = _publish_and_create(service, suffix)
    service.evaluate(
        PRIMARY,
        created.binding_id,
        EvaluateOperationalBindingRequest(expected_version=1, dependencies=dependencies()),
        idempotency_key=f"evaluate-{suffix}",
        actor="pytest",
        evaluated_at=evaluation_time,
    )
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="operational"):
        service.update(
            PRIMARY,
            created.binding_id,
            UpdateCapabilityBindingRequest(
                expected_version=2,
                from_status="provisioning",
                to_status="active",
                health="healthy",
                observed_at=datetime.now(UTC),
            ),
            idempotency_key=f"expired-{suffix}",
            actor="pytest",
        )
