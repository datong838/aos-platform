import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ao_continuation_router.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ao_continuation_router", PATH)
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


def _snapshot(state="succeeded", definition_state="disabled", definition_revision=60):
    return {
        "attemptId": "67c2331d-b73f-4863-b881-0d67e6c55508",
        "attemptCount": 2,
        "operationKey": "snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1",
        "idempotencyKey": "snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:2",
        "requestHash": "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7",
        "originalAttemptState": "abandoned",
        "originalTerminalReason": "ATTEMPT_LEASE_EXPIRED",
        "installationId": "d4186607-c93f-4fd0-8daa-46e349184ab9",
        "generation": "00bb99df-d436-483d-86df-496718c6f129",
        "operationKind": "recoverable_store",
        "state": state,
        "revision": 200,
        "completedAt": "2026-09-19T04:00:00+00:00" if state == "succeeded" else None,
        "observedAt": "2026-09-19T04:00:00+00:00",
        "heartbeatAt": "2026-09-19T03:59:50+00:00",
        "leaseUntil": "2026-09-19T04:01:00+00:00",
        "definitionRevision": definition_revision,
        "definitionState": definition_state,
        "recoveryRevision": 19,
        "manifestHash": "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01",
        "members": 12,
        "runningRuns": 0 if state == "succeeded" else 12,
        "succeededRuns": 12 if state == "succeeded" else 0,
        "failedRuns": 0,
        "datasetReceipts": 12,
        "relationships": 1,
        "linkCommands": 1,
        "linkCount": 1168,
        "retirements": 1 if state == "succeeded" else 0,
        "linkStoreReceipts": 1 if state == "succeeded" else 0,
        "ecomLinks": 1168 if state == "succeeded" else 0,
        "linkOutbox": 1168 if state == "succeeded" else 0,
        "projectionPending": 0,
        "liveResources": 3,
        "devOrgCanary": 0,
        "routes": 9,
        "controlSecondsRemaining": 1000,
        "controlExpired": False,
    }


def _artifacts(**values):
    result = {
        "recoveryClosed": True,
        "v3Preflight": False,
        "v3Approval": False,
        "v3Put": False,
        "v3Disable": False,
        "v3DisableApproval": False,
        "v3DisablePut": False,
    }
    result.update(values)
    return result


def test_running_and_terminal_attempt_routes_are_deterministic():
    running = _snapshot("running", "enabled", 59)
    assert router.classify(running, {}, attempt_guard={
        "outcome": "RUNNING_HEALTHY_NO_ACTION", "automaticAction": False,
        "heartbeatHealthy": True,
    })["nextAction"] == "OBSERVE_AO_RECOVERY"

    assert router.classify(running, {}, attempt_guard={
        "outcome": "RUNNING_HEARTBEAT_ONLY_DIAGNOSE", "automaticAction": False,
        "heartbeatHealthy": True, "executionLimitExceeded": True,
    })["nextAction"] == "DIAGNOSE_AO_BOUNDED_EXECUTION"

    succeeded = _snapshot("succeeded", "enabled", 59)
    assert router.classify(succeeded, {}, attempt_guard={
        "outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False,
    })["nextAction"] == "RUN_AO_INSPECT_THEN_DISABLE"

    failed = _snapshot("failed", "enabled", 59)
    failed["runningRuns"] = 0
    failed["failedRuns"] = 12
    assert router.classify(failed, {}, attempt_guard={
        "outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False,
    })["nextAction"] == "FREEZE_AO_FAILURE_BOUNDARY"

    abandoned = _snapshot("abandoned", "enabled", 59)
    assert router.classify(abandoned, {}, attempt_guard={
        "outcome": "ABANDONED_WAIT_NATURAL_SUCCESSOR", "automaticAction": False,
    })["nextAction"] == "WAIT_AO_NATURAL_SUCCESSOR"


@pytest.mark.parametrize(
    ("artifacts", "expected"),
    [
        (_artifacts(), "RUN_POLICY_V3_PREFLIGHT"),
        (_artifacts(v3Preflight=True), "RUN_POLICY_V3_APPROVAL"),
        (_artifacts(v3Preflight=True, v3Approval=True), "RUN_POLICY_V3_PUT"),
    ],
)
def test_closed_recovery_routes_each_v3_write_step(artifacts, expected):
    result = router.classify(
        _snapshot(), artifacts, policy={"revision": 2, "enabled": True}
    )
    assert result["nextAction"] == expected
    assert result["automaticAction"] is False


@pytest.mark.parametrize(
    ("artifacts", "phase", "expected"),
    [
        (_artifacts(v3Preflight=True, v3Approval=True, v3Put=True), "occurrence_pending", "OBSERVE_POLICY_V3_NATURAL_CHAIN"),
        (_artifacts(v3Preflight=True, v3Approval=True, v3Put=True), "growth_plan_ready", "RUN_POLICY_V3_DISABLE_READINESS"),
        (_artifacts(v3Preflight=True, v3Approval=True, v3Put=True, v3Disable=True), "growth_plan_ready", "RUN_POLICY_V4_DISABLE_APPROVAL"),
        (_artifacts(v3Preflight=True, v3Approval=True, v3Put=True, v3Disable=True, v3DisableApproval=True), "growth_plan_ready", "RUN_POLICY_V4_DISABLE_PUT"),
    ],
)
def test_v3_natural_chain_routes_each_terminal_step(artifacts, phase, expected):
    result = router.classify(
        _snapshot(), artifacts, policy={"revision": 3, "enabled": True}, phase=phase
    )
    assert result["nextAction"] == expected


def test_disabled_v4_opens_plan_review_only_with_exact_put_artifact():
    result = router.classify(
        _snapshot(), _artifacts(
            v3Preflight=True, v3Approval=True, v3Put=True,
            v3Disable=True, v3DisableApproval=True, v3DisablePut=True,
        ),
        policy={"revision": 4, "enabled": False},
    )
    assert result["nextAction"] == "START_FIRST_CHAIN_PLAN_REVIEW"


def test_unknown_or_inconsistent_state_fails_closed():
    with pytest.raises(RuntimeError, match="closure"):
        router.classify(
            _snapshot(), _artifacts(recoveryClosed=False),
            policy={"revision": 2, "enabled": True},
        )
    with pytest.raises(RuntimeError, match="put outcome"):
        router.classify(
            _snapshot(), _artifacts(v3Preflight=True, v3Approval=True, v3Put=True),
            policy={"revision": 2, "enabled": True},
        )
    with pytest.raises(RuntimeError, match="canonical put"):
        router.classify(
            _snapshot(), _artifacts(), policy={"revision": 4, "enabled": False}
        )
    with pytest.raises(RuntimeError, match="artifact prefix"):
        router.classify(
            _snapshot(), _artifacts(v3Approval=True),
            policy={"revision": 2, "enabled": True},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("installationId", "wrong-installation"),
        ("generation", "wrong-generation"),
        ("operationKind", "wrong-operation"),
        ("recoveryRevision", 18),
        ("manifestHash", "sha256:wrong"),
        ("succeededRuns", 11),
        ("datasetReceipts", 11),
        ("linkStoreReceipts", 0),
        ("ecomLinks", 1167),
        ("projectionPending", 1),
        ("routes", 8),
        ("liveResources", 2),
        ("devOrgCanary", 1),
        ("completedAt", None),
    ],
)
def test_closed_recovery_rejects_current_authority_drift(field, value):
    snapshot = _snapshot()
    snapshot[field] = value
    with pytest.raises(RuntimeError, match="closed-runtime authority"):
        router.classify(
            snapshot, _artifacts(), policy={"revision": 2, "enabled": True}
        )


def test_router_source_is_read_only_and_never_runs_an_executor():
    source = PATH.read_text(encoding="utf-8")
    assert '"automaticAction": False' in source
    assert '"sourceReads": 0' in source
    assert '"businessWrites": 0' in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source
    assert "router.dispatch" not in source
    assert "run_definition" not in source


def test_router_module_import_has_no_stdout_and_main_contract_is_single_json():
    command = [sys.executable, "-c", (
        "import importlib.util;"
        f"s=importlib.util.spec_from_file_location('router',{str(PATH)!r});"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "m.observe=lambda:(print('runtime-log'),{'outcome':'TEST_ROUTED'})[1];"
        "raise SystemExit(m.main())"
    )]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    assert json.loads(result.stdout) == {"outcome": "TEST_ROUTED"}
    assert "runtime-log" in result.stderr
