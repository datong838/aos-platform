from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    OperationalBindingDependencies,
    VersionedAssetRef,
)

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/bootstrap_r2_d03_binding_composition.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r2_d03_binding_composition", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_plan_freezes_one_d03_chain_without_provider_call() -> None:
    plan = MODULE.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["providerCalls"] == 0
    assert plan["secretPayloadReads"] == 0
    assert plan["order"] == [
        "CapabilityBinding create/evaluate/activate",
        "AgentInstance activate",
        "SkillBinding create/evaluate/activate",
    ]


def test_health_blocker_is_stable_and_specific() -> None:
    assert (
        MODULE.runtime_blocker_code(["provider_health_unavailable_or_stale"])
        == "PROVIDER_HEALTH_REFRESH_REQUIRED"
    )
    assert MODULE.runtime_blocker_code(["eval_gate_expired"]) == "MODEL_RUNTIME_NOT_READY"


def test_exact_revision_string_keeps_full_hash() -> None:
    ref = VersionedAssetRef(
        asset_type="NetworkPolicyRevision",
        asset_id="network-qyh-text-dev",
        revision=1,
        content_hash="a" * 64,
    )
    assert MODULE.compact_revision(ref) == f"network-qyh-text-dev@1#{'a' * 64}"


def test_dry_run_fails_closed_before_any_write_when_health_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {"capabilityBinding": 0, "skillBinding": 0, "agentRun": 0}
    monkeypatch.setattr(MODULE, "_counts", lambda scope: counts.copy())

    def blocked(*, evaluated_at):
        raise MODULE.CompositionBlocked(
            "PROVIDER_HEALTH_REFRESH_REQUIRED",
            ["provider_health_unavailable_or_stale"],
        )

    monkeypatch.setattr(MODULE, "load_exact_composition", blocked)
    result = MODULE.inspect()
    assert result["status"] == "blocked"
    assert result["blockerCode"] == "PROVIDER_HEALTH_REFRESH_REQUIRED"
    assert result["sideEffectCounts"] == counts


def test_apply_stops_before_binding_services_when_health_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        MODULE,
        "_counts",
        lambda scope: {"capabilityBinding": 0, "skillBinding": 0, "agentRun": 0},
    )

    def blocked(*, evaluated_at):
        raise MODULE.CompositionBlocked("PROVIDER_HEALTH_REFRESH_REQUIRED")

    monkeypatch.setattr(MODULE, "load_exact_composition", blocked)
    with pytest.raises(MODULE.CompositionBlocked) as exc:
        MODULE.apply()
    assert exc.value.code == "PROVIDER_HEALTH_REFRESH_REQUIRED"


def _ref(asset_type: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=asset_id,
        revision=1,
        content_hash="a" * 64,
    )


def test_skill_dependencies_use_skill_release_gate_not_route_gate() -> None:
    route_gate = _ref("EvalGateDecision", "route-gate")
    skill_gate = _ref("EvalGateDecision", "skill-gate")
    route_ref = _ref("ModelRouteRevision", "route-1")
    policy_ref = _ref("RuntimePolicyRevision", "policy-1")
    composition = SimpleNamespace(
        skill=SimpleNamespace(
            release_gate_ref=skill_gate,
            model_route_ref=route_ref,
            runtime_policy_ref=policy_ref,
        ),
        dependencies=OperationalBindingDependencies(
            model_route_ref=route_ref,
            runtime_policy_ref=policy_ref,
            eval_gate_ref=route_gate,
            budget_policy_ref=_ref("BudgetPolicyRevision", "budget-1"),
        ),
    )

    dependencies = MODULE.skill_binding_dependencies(composition)

    assert dependencies.eval_gate_ref == skill_gate
    assert dependencies.eval_gate_ref != route_gate


def test_resume_evaluates_current_version_then_activates_returned_version() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    dependencies = OperationalBindingDependencies(
        model_route_ref=_ref("ModelRouteRevision", "route-1"),
        runtime_policy_ref=_ref("RuntimePolicyRevision", "policy-1"),
        eval_gate_ref=_ref("EvalGateDecision", "skill-gate"),
        budget_policy_ref=_ref("BudgetPolicyRevision", "budget-1"),
    )
    current = SimpleNamespace(
        binding_id="binding-1",
        status="provisioning",
        version=2,
        readiness=CapabilityReadiness.BLOCKED,
        dependencies=OperationalBindingDependencies(),
        dependency_snapshot_hash="old",
        readiness_expires_at=now + timedelta(minutes=5),
    )
    evaluated = SimpleNamespace(
        **{
            **current.__dict__,
            "version": 3,
            "readiness": CapabilityReadiness.AVAILABLE,
            "dependencies": dependencies,
            "dependency_snapshot_hash": "new",
        }
    )
    activated = SimpleNamespace(**{**evaluated.__dict__, "version": 4, "status": "active"})

    class FakeService:
        def evaluate_binding(self, _scope, _binding_id, request, **_kwargs):
            assert request.expected_version == 2
            assert request.dependencies == dependencies
            readiness = SimpleNamespace(
                readiness=CapabilityReadiness.AVAILABLE, reasons=[]
            )
            return evaluated, readiness, SimpleNamespace()

        def update_binding(self, _scope, _binding_id, request, **_kwargs):
            assert request.expected_version == 3
            return activated, SimpleNamespace()

    result = MODULE.ensure_skill_binding_active(
        service=FakeService(),
        binding=current,
        dependencies=dependencies,
        decision_at=now,
    )

    assert result.status == "active"
    assert result.version == 4


def test_resume_does_not_replay_timestamped_capability_activation() -> None:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    binding = SimpleNamespace(status="active", binding_id="capability-1")
    readiness = SimpleNamespace(
        readiness=CapabilityReadiness.AVAILABLE,
        reasons=[],
        expires_at=now + timedelta(minutes=5),
    )

    class NoWriteService:
        def update(self, *_args, **_kwargs):
            raise AssertionError("active capability binding must not be updated again")

    result = MODULE.ensure_capability_binding_active(
        service=NoWriteService(),
        binding=binding,
        readiness=readiness,
        decision_at=now,
    )

    assert result is binding
