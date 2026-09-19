"""AP guard freezes one natural attempt and never becomes execution authority."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ap_attempt_guard.py"
SPEC = importlib.util.spec_from_file_location("a0v_ap_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 5, 50, tzinfo=UTC)
    value = {
        "attemptId": guard.SECOND_ATTEMPT_ID,
        "attemptCount": 2,
        "operationKey": guard.OPERATION_KEY,
        "idempotencyKey": guard.BASE_IDEMPOTENCY_KEY + ":2",
        "requestHash": guard.REQUEST_HASH,
        "terminalReason": None,
        "terminalErrorType": None,
        "firstAttemptId": guard.ATTEMPT_ID,
        "firstAttemptState": "failed",
        "firstTerminalReason": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        "firstTerminalErrorType": "IngressJournalConflict",
        "installationId": guard.successor.AP_ID,
        "generation": guard.successor.AP_GENERATION,
        "operationKind": "recoverable_store",
        "state": "running",
        "revision": 7,
        "acceptedAt": observed - timedelta(seconds=120),
        "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10),
        "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed,
        "controlSecondsRemaining": 18000,
        "controlExpired": False,
        "definitionRevision": 62,
        "definitionState": "enabled",
        "recoveryRevision": 20,
        "manifestHash": guard.recovery.MANIFEST,
        "members": 12,
        "runningRuns": 12,
        "succeededRuns": 0,
        "failedRuns": 0,
        "datasetReceipts": 12,
        "relationships": 1,
        "linkCommands": 1,
        "linkCount": 1168,
        "retirements": 0,
        "linkStoreReceipts": 0,
        "ecomLinks": 0,
        "linkOutbox": 0,
        "projectionPending": 0,
        "routes": 9,
        "liveResources": 3,
        "devOrgCanary": 0,
    }
    value.update(changes)
    return value


def test_healthy_running_attempt_is_observation_only():
    assert guard.classify(facts()) == {
        "outcome": "RUNNING_HEALTHY_NO_ACTION",
        "automaticAction": False,
        "heartbeatHealthy": True,
    }


def test_bounded_execution_diagnosis_never_resends():
    result = guard.classify(facts(attemptElapsedSeconds=301))
    assert result["outcome"] == "RUNNING_HEARTBEAT_ONLY_DIAGNOSE"
    assert result["automaticAction"] is False


def test_terminal_success_requires_complete_store_and_run_closure():
    result = guard.classify(facts(
        state="succeeded", runningRuns=0, succeededRuns=12,
        retirements=1, linkStoreReceipts=1, ecomLinks=1168,
        linkOutbox=1168, projectionPending=0,
    ))
    assert result == {"outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False}


@pytest.mark.parametrize(("field", "value"), (
    ("attemptCount", 3),
    ("attemptId", "wrong"),
    ("definitionRevision", 61),
    ("recoveryRevision", 19),
    ("datasetReceipts", 11),
    ("routes", 8),
    ("devOrgCanary", 1),
))
def test_identity_or_boundary_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="AP guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_partial_success_fails_closed():
    with pytest.raises(RuntimeError, match="AP guard authority differs"):
        guard.classify(facts(state="succeeded", runningRuns=0, succeededRuns=12))


def test_failed_attempt_requires_exact_terminal_boundary():
    result = guard.classify(facts(
        state="failed", terminalReason="RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        terminalErrorType="IngressJournalConflict",
    ))
    assert result == {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}
    with pytest.raises(RuntimeError, match="AP guard authority differs"):
        guard.classify(facts(state="failed", terminalReason="wrong", terminalErrorType="IngressJournalConflict"))


def test_exact_failed_then_abandoned_chain_requires_pause():
    result = guard.classify(facts(
        state="abandoned", terminalReason="ATTEMPT_LEASE_EXPIRED",
        terminalErrorType=None, heartbeatAt=None, leaseUntil=None,
    ))
    assert result == {"outcome": "FAILED_CHAIN_PAUSE_REQUIRED", "automaticAction": False}


def test_script_is_select_only_and_has_no_business_action():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"\b(?:insert|update|delete|call|run_definition|transition|register_successor)\b",
        re.IGNORECASE,
    )
    assert forbidden.search(source) is None
    assert "consumer_connection" in source
    assert "SELECT" in source
