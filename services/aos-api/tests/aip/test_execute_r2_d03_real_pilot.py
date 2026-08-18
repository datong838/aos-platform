from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "execute_r2_d03_real_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("execute_r2_d03_real_pilot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_plan_freezes_one_business_call_and_no_sensitive_output() -> None:
    plan = MODULE.build_plan()
    assert plan["providerBusinessCallLimit"] == 1
    assert plan["secretPayloadReads"] == 0
    assert plan["externalBusinessActions"] == 0
    assert plan["sensitiveBodiesPrinted"] == 0
    assert "query" not in plan and "answer" not in plan


def test_r2_4f_uses_new_v4_authority_and_preserves_v1_v2_v3_incident_chain() -> None:
    plan = MODULE.build_plan()
    assert MODULE.APPROVAL_REF == "46-R2-4F-V4-SINGLE-PROVIDER-CALL-APPROVED"
    assert MODULE.AGENT_RUN_ID.endswith("real-pilot.v4")
    assert MODULE.ATTEMPT_ID.endswith("real-pilot.v4.attempt-1")
    assert MODULE.EXECUTE_KEY.endswith("execute-v4")
    assert MODULE.INCIDENT_AGENT_RUN_ID.endswith("real-pilot.v3")
    assert MODULE.INCIDENT_ATTEMPT_ID.endswith("real-pilot.v3.attempt-1")
    assert MODULE.PRIOR_INCIDENT_V2_AGENT_RUN_ID.endswith("real-pilot.v2")
    assert MODULE.PRIOR_INCIDENT_V2_ATTEMPT_ID.endswith("real-pilot.v2.attempt-1")
    assert MODULE.EARLIER_INCIDENT_AGENT_RUN_ID.endswith("real-pilot.v1")
    assert MODULE.EARLIER_INCIDENT_ATTEMPT_ID.endswith("real-pilot.attempt-1")
    assert plan["recoveryOf"] == {
        "agentRunId": MODULE.INCIDENT_AGENT_RUN_ID,
        "attemptId": MODULE.INCIDENT_ATTEMPT_ID,
        "status": "unknown",
    }
    assert plan["priorIncidents"] == [
        {
            "agentRunId": MODULE.EARLIER_INCIDENT_AGENT_RUN_ID,
            "attemptId": MODULE.EARLIER_INCIDENT_ATTEMPT_ID,
            "status": "unknown",
        },
        {
            "agentRunId": MODULE.PRIOR_INCIDENT_V2_AGENT_RUN_ID,
            "attemptId": MODULE.PRIOR_INCIDENT_V2_ATTEMPT_ID,
            "status": "unknown",
        },
        plan["recoveryOf"],
    ]
    assert MODULE.AGENT_RUN_ID != MODULE.INCIDENT_AGENT_RUN_ID
    assert MODULE.ATTEMPT_ID != MODULE.INCIDENT_ATTEMPT_ID
    assert MODULE.AGENT_RUN_ID != MODULE.PRIOR_INCIDENT_V2_AGENT_RUN_ID
    assert MODULE.AGENT_RUN_ID != MODULE.EARLIER_INCIDENT_AGENT_RUN_ID


def test_active_binding_readiness_refresh_is_supported_without_lifecycle_write() -> None:
    capability_source = (
        Path(__file__).resolve().parents[2]
        / "aos_api"
        / "aip_capability_binding_service.py"
    ).read_text()
    skill_source = (
        Path(__file__).resolve().parents[2] / "aos_api" / "aip_skill_registry.py"
    ).read_text()
    expected = "status IN ('provisioning','active','suspended')"
    assert expected in capability_source
    assert expected in skill_source
    assert "SET status=" not in capability_source.split("def evaluate(", 1)[1].split(
        "def get(", 1
    )[0]
    assert "SET status=" not in skill_source.split("def evaluate_binding(", 1)[1].split(
        "def preview_binding(", 1
    )[0]


def test_fresh_binding_readiness_replay_is_read_only(monkeypatch) -> None:
    now = datetime(2026, 8, 18, 4, 45, tzinfo=UTC)
    capability = SimpleNamespace(
        status="active",
        operational_readiness=MODULE.CapabilityReadiness.AVAILABLE,
        readiness_expires_at=now + timedelta(minutes=5),
        dependency_snapshot_hash="capability-snapshot",
    )
    skill = SimpleNamespace(
        status="active",
        readiness=MODULE.CapabilityReadiness.AVAILABLE,
        readiness_expires_at=now + timedelta(minutes=5),
        dependency_snapshot_hash="skill-snapshot",
    )

    class Result:
        def fetchone(self):
            return {
                "observation_id": "health-current",
                "expires_at": now + timedelta(minutes=10),
            }

    class Conn:
        def execute(self, *_args):
            return Result()

    class Context:
        def __enter__(self):
            return Conn()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(MODULE, "db_connect", lambda _scope: Context())
    monkeypatch.setattr(
        MODULE.AipCapabilityBindingService, "get", lambda *_args: capability
    )
    monkeypatch.setattr(MODULE.AipSkillRegistry, "get_binding", lambda *_args: skill)
    monkeypatch.setattr(
        MODULE.AipCapabilityBindingService,
        "evaluate",
        lambda *_args, **_kwargs: pytest.fail("fresh replay must not write capability"),
    )
    monkeypatch.setattr(
        MODULE.AipSkillRegistry,
        "evaluate_binding",
        lambda *_args, **_kwargs: pytest.fail("fresh replay must not write skill"),
    )

    assert MODULE.refresh_active_binding_readiness(now=now) == {
        "healthObservationId": "health-current",
        "capabilitySnapshotHash": "capability-snapshot",
        "skillSnapshotHash": "skill-snapshot",
    }


def test_readback_result_never_contains_prompt_or_answer(monkeypatch) -> None:
    attempt = SimpleNamespace(
        attempt_id=MODULE.ATTEMPT_ID,
        status=SimpleNamespace(value="succeeded"),
        provider_receipt_id="provider-receipt-1",
        usage_receipt_ids=["usage-1"],
        output_artifact_ref=SimpleNamespace(
            artifact_id="artifact-1", content_hash="a" * 64
        ),
        lineage_id="lineage-1",
    )
    response = SimpleNamespace(
        agent_run=SimpleNamespace(
            agent_run_id=MODULE.AGENT_RUN_ID,
            status=SimpleNamespace(value="succeeded"),
        ),
        answer="must-not-be-returned",
        replayed=False,
    )
    task_run = SimpleNamespace(id="task-run-1", status=SimpleNamespace(value="succeeded"))
    monkeypatch.setattr(
        MODULE.AipAgentRunExecutionService, "get", lambda *_args: attempt
    )

    class Result:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class Conn:
        calls = 0

        def execute(self, _query, _args):
            self.calls += 1
            if self.calls == 1:
                return Result({"n": 1})
            if self.calls == 2:
                return Result({"n": 1})
            if self.calls == 3:
                return Result({"n": 2})
            return Result({"status": "released"})

    class Context:
        def __enter__(self):
            return Conn()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(MODULE, "db_connect", lambda _scope: Context())
    monkeypatch.setattr(
        MODULE, "_counts", lambda _scope: {"agentRun": 0, "attempt": 0, "skillBinding": 0}
    )
    result = MODULE._readback(response, task_run)
    encoded = str(result).lower()
    assert "must-not-be-returned" not in encoded
    assert "query" not in result and "answer" not in result
    assert result["answerLength"] == len(response.answer)


def test_apply_stops_before_provider_when_canary_is_dirty(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_counts",
        lambda scope: {
            "agentRun": 1 if scope == MODULE.CANARY_SCOPE else 0,
            "attempt": 0,
            "skillBinding": 0,
        },
    )
    monkeypatch.setattr(
        MODULE,
        "load_authority",
        lambda **_kwargs: pytest.fail("authority must not load after dirty canary"),
    )
    with pytest.raises(MODULE.PilotBlocked, match="NEGATIVE_CANARY_DIRTY"):
        MODULE.apply()


def test_apply_never_executes_when_authority_is_blocked(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_counts",
        lambda _scope: {"agentRun": 0, "attempt": 0, "skillBinding": 0},
    )
    monkeypatch.setattr(
        MODULE,
        "refresh_active_binding_readiness",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(MODULE, "_existing_terminal_attempt", lambda: None)
    monkeypatch.setattr(
        MODULE,
        "load_authority",
        lambda **_kwargs: (_ for _ in ()).throw(
            MODULE.PilotBlocked("MODEL_RUNTIME_NOT_READY")
        ),
    )
    monkeypatch.setattr(
        MODULE.AipAgentRunExecutor,
        "execute",
        lambda *_args, **_kwargs: pytest.fail("Provider path must not execute"),
    )
    with pytest.raises(MODULE.PilotBlocked, match="MODEL_RUNTIME_NOT_READY"):
        MODULE.apply()


def test_apply_never_refreshes_or_reinvokes_a_terminal_attempt(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_counts",
        lambda _scope: {"agentRun": 0, "attempt": 0, "skillBinding": 0},
    )
    monkeypatch.setattr(
        MODULE,
        "_existing_terminal_attempt",
        lambda: {"attemptStatus": "unknown", "reasonCode": "PROVIDER_RESULT_UNKNOWN"},
    )
    monkeypatch.setattr(
        MODULE,
        "refresh_active_binding_readiness",
        lambda **_kwargs: pytest.fail("terminal replay must stay read-only"),
    )
    monkeypatch.setattr(
        MODULE.AipAgentRunExecutor,
        "execute",
        lambda *_args, **_kwargs: pytest.fail("Provider path must not execute"),
    )
    with pytest.raises(MODULE.PilotBlocked, match="EXISTING_ATTEMPT_TERMINAL"):
        MODULE.apply()
