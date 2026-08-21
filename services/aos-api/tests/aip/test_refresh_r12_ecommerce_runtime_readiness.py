from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/refresh_r12_ecommerce_runtime_readiness.py"
)
SPEC = importlib.util.spec_from_file_location("refresh_r12_runtime", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)


def successful(role: str, expected_status: str):
    def run(*, now):
        assert now == NOW
        return {
            "status": expected_status,
            "activeSkillBindingCount": 6,
            "capabilityBindings": [{"bindingId": f"cap-{role}"}],
            "negativeCanaryCounts": {"skillBindings": 0},
            "providerCalls": 0,
            "agentRunsCreated": 0,
            "secretPayloadReads": 0,
        }

    return run


def successful_d03(*, now):
    assert now == NOW
    return {
        "status": "R12_D03_READINESS_METADATA_GREEN",
        "bindingId": MODULE.D03_BINDING_ID,
        "providerCalls": 0,
        "agentRunsCreated": 0,
        "secretPayloadReads": 0,
    }


def test_default_plan_is_read_only_and_lists_six_roles():
    plan = MODULE.build_plan()
    assert plan["status"] == "planned"
    assert len(plan["roles"]) == 6
    assert plan["providerCalls"] == plan["agentRuns"] == 0
    assert plan["secretPayloadReads"] == 0


def test_loader_resolves_six_reviewed_apply_contracts():
    loaded = MODULE._load_refreshers()
    assert [(role, status) for role, status, _ in loaded] == [
        (role, status) for role, _, status in MODULE.ROLE_REFRESHERS
    ]
    assert all(callable(refresh) for _, _, refresh in loaded)


def test_apply_composes_all_roles_without_provider_or_agent_run():
    refreshers = [
        (role, expected, successful(role, expected))
        for role, _, expected in MODULE.ROLE_REFRESHERS
    ]
    result = MODULE.apply(
        now=NOW, refreshers=refreshers, d03_refresh=successful_d03
    )
    assert result["status"] == "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN"
    assert result["completedRoles"] == [item[0] for item in MODULE.ROLE_REFRESHERS]
    assert result["providerCalls"] == result["agentRunsCreated"] == 0
    assert result["externalActions"] == result["secretPayloadReads"] == 0
    assert result["immutableD03"]["bindingId"] == MODULE.D03_BINDING_ID


def test_apply_reports_partial_progress_and_stops_after_first_failure():
    calls = []

    def first(*, now):
        calls.append("first")
        return {
            "status": "GREEN-1",
            "providerCalls": 0,
            "agentRunsCreated": 0,
            "secretPayloadReads": 0,
        }

    def fail(*, now):
        calls.append("fail")
        raise RuntimeError("blocked")

    def forbidden(*, now):
        calls.append("forbidden")
        return {"status": "GREEN-3"}

    with pytest.raises(MODULE.R12RuntimeRefreshBlocked) as exc:
        MODULE.apply(
            now=NOW,
            refreshers=[
                ("first", "GREEN-1", first),
                ("fail", "GREEN-2", fail),
                ("forbidden", "GREEN-3", forbidden),
            ],
            d03_refresh=successful_d03,
        )
    assert exc.value.code == "ROLE_RUNTIME_REFRESH_FAILED"
    assert exc.value.completed_roles == ["first"]
    assert calls == ["first", "fail"]


def test_apply_fails_closed_when_role_reports_forbidden_side_effect():
    def unsafe(*, now):
        return {
            "status": "GREEN",
            "providerCalls": 1,
            "agentRunsCreated": 0,
            "secretPayloadReads": 0,
        }

    with pytest.raises(MODULE.R12RuntimeRefreshBlocked) as exc:
        MODULE.apply(
            now=NOW,
            refreshers=[("unsafe", "GREEN", unsafe)],
            d03_refresh=successful_d03,
        )
    assert exc.value.code == "FORBIDDEN_SIDE_EFFECT_REPORTED"


def test_apply_fails_closed_when_immutable_d03_refresh_reports_agent_run():
    def unsafe_d03(*, now):
        return {
            "status": "R12_D03_READINESS_METADATA_GREEN",
            "providerCalls": 0,
            "agentRunsCreated": 1,
            "secretPayloadReads": 0,
        }

    with pytest.raises(MODULE.R12RuntimeRefreshBlocked) as exc:
        MODULE.apply(now=NOW, refreshers=[], d03_refresh=unsafe_d03)
    assert exc.value.code == "FORBIDDEN_SIDE_EFFECT_REPORTED"
    assert exc.value.details[:2] == ["D03", "agentRunsCreated"]
