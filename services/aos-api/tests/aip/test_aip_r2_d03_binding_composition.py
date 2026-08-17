from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef

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
