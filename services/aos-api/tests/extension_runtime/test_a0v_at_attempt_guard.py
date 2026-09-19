"""AT guard observes one natural attempt and never executes business work."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_at_attempt_guard.py"
import sys
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("a0v_at_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 6, 38, tzinfo=UTC)
    value = {
        "attemptId": guard.ORIGINAL_ATTEMPT_ID, "attemptCount": 1,
        "operationKey": guard.OPERATION_KEY, "idempotencyKey": guard.BASE_IDEMPOTENCY_KEY + ":1",
        "requestHash": guard.REQUEST_HASH, "terminalReason": None, "terminalErrorType": None,
        "installationId": guard.successor.AT_ID, "generation": guard.successor.AT_GENERATION,
        "operationKind": "recoverable_store", "state": "running", "revision": 2,
        "acceptedAt": observed - timedelta(seconds=120), "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10), "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed, "controlSecondsRemaining": 18000, "controlExpired": False,
        "definitionRevision": 72, "definitionState": "enabled", "recoveryRevision": 23,
        "manifestHash": guard.recovery.MANIFEST, "members": 12, "runningRuns": 12,
        "succeededRuns": 0, "failedRuns": 0, "datasetReceipts": 12, "relationships": 1,
        "linkCommands": 1, "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0, "routes": 9,
        "liveResources": 3, "devOrgCanary": 0,
        "attemptHistory": [{
            "attempt_id": guard.ORIGINAL_ATTEMPT_ID,
            "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":1",
            "request_hash": guard.REQUEST_HASH,
            "state": "running",
            "terminal_reason_code": None,
            "terminal_error_type": None,
        }],
    }
    value.update(changes)
    value["attemptHistory"][-1] = value["attemptHistory"][-1] | {
        "state": value["state"],
        "terminal_reason_code": value["terminalReason"],
        "terminal_error_type": value["terminalErrorType"],
    }
    return value


def test_running_healthy_is_observation_only():
    assert guard.classify(facts()) == {"outcome": "RUNNING_HEALTHY_NO_ACTION",
        "automaticAction": False, "heartbeatHealthy": True}


def test_running_without_heartbeat_is_stale_diagnosis_only():
    result = guard.classify(facts(heartbeatAt=None))
    assert result == {"outcome": "RUNNING_STALE_DIAGNOSE_ONLY",
        "automaticAction": False, "heartbeatHealthy": False}


def test_elapsed_without_store_progress_only_diagnoses():
    result = guard.classify(facts(attemptElapsedSeconds=301))
    assert result["outcome"] == "RUNNING_HEARTBEAT_ONLY_DIAGNOSE"
    assert result["automaticAction"] is False


def test_success_requires_strict_store_and_run_closure():
    result = guard.classify(facts(state="succeeded", runningRuns=0, succeededRuns=12,
        retirements=1, linkStoreReceipts=1, ecomLinks=1168, linkOutbox=1168, projectionPending=0))
    assert result == {"outcome": "SUCCEEDED_STRICT_CLOSURE", "automaticAction": False}
    with pytest.raises(RuntimeError, match="AT guard authority differs"):
        guard.classify(facts(state="succeeded", runningRuns=0, succeededRuns=12))


def test_deadline_failed_chain_requires_pause_and_never_executes():
    assert guard.classify(facts(state="failed",
        terminalReason="RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        terminalErrorType="IngressJournalConflict")) == {
        "outcome": "FAILED_CHAIN_PAUSE_REQUIRED", "automaticAction": False}
    with pytest.raises(RuntimeError, match="AT guard authority differs"):
        guard.classify(facts(state="failed", terminalReason=None, terminalErrorType="RuntimeError"))
    assert guard.classify(facts(state="abandoned", terminalReason="ATTEMPT_LEASE_EXPIRED")) == {
        "outcome": "ABANDONED_WAIT_NATURAL_SUCCESSOR", "automaticAction": False}


@pytest.mark.parametrize(("field", "value"), (("attemptCount", 2), ("attemptId", "wrong"),
    ("definitionRevision", 71), ("recoveryRevision", 22), ("datasetReceipts", 11),
    ("routes", 8), ("devOrgCanary", 1)))
def test_identity_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="AT guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_third_natural_attempt_requires_exact_failed_predecessors():
    current = facts(
        attemptId=guard.THIRD_ATTEMPT_ID,
        attemptCount=3,
        idempotencyKey=guard.BASE_IDEMPOTENCY_KEY + ":3",
    )
    current["attemptHistory"] = [
        {"attempt_id": guard.ORIGINAL_ATTEMPT_ID,
         "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":1",
         "request_hash": guard.REQUEST_HASH, "state": "failed",
         "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
         "terminal_error_type": "IngressJournalConflict"},
        {"attempt_id": guard.SECOND_ATTEMPT_ID,
         "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":2",
         "request_hash": guard.REQUEST_HASH, "state": "failed",
         "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
         "terminal_error_type": "IngressJournalConflict"},
        {"attempt_id": guard.THIRD_ATTEMPT_ID,
         "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":3",
         "request_hash": guard.REQUEST_HASH, "state": "running",
         "terminal_reason_code": None, "terminal_error_type": None},
    ]
    assert guard.classify(current)["outcome"] == "RUNNING_HEALTHY_NO_ACTION"
    current["attemptHistory"][1]["terminal_reason_code"] = "OTHER"
    with pytest.raises(RuntimeError, match="AT guard authority differs"):
        guard.classify(current)


def test_fourth_cancelled_attempt_is_exact_pause_boundary():
    current = facts(
        attemptId=guard.FOURTH_ATTEMPT_ID,
        attemptCount=4,
        idempotencyKey=guard.BASE_IDEMPOTENCY_KEY + ":4",
        state="failed",
        terminalReason="RECOVERABLE_INGRESS_CANCELLED",
        terminalErrorType="IngressJournalConflict",
    )
    failed = lambda attempt, ordinal: {
        "attempt_id": attempt,
        "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + f":{ordinal}",
        "request_hash": guard.REQUEST_HASH,
        "state": "failed",
        "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        "terminal_error_type": "IngressJournalConflict",
    }
    current["attemptHistory"] = [
        failed(guard.ORIGINAL_ATTEMPT_ID, 1),
        failed(guard.SECOND_ATTEMPT_ID, 2),
        failed(guard.THIRD_ATTEMPT_ID, 3),
        {"attempt_id": guard.FOURTH_ATTEMPT_ID,
         "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":4",
         "request_hash": guard.REQUEST_HASH, "state": "failed",
         "terminal_reason_code": "RECOVERABLE_INGRESS_CANCELLED",
         "terminal_error_type": "IngressJournalConflict"},
    ]
    assert guard.classify(current) == {
        "outcome": "FAILED_CHAIN_PAUSE_REQUIRED", "automaticAction": False,
    }


def test_script_is_select_only_and_has_no_business_action():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition|register_successor)\b", re.I)
    assert forbidden.search(source) is None
    assert "consumer_connection" in source and "SELECT" in source
