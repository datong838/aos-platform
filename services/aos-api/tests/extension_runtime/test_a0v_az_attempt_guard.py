"""AZ guard observes one natural attempt and never executes business work."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_az_attempt_guard.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_az_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 14, 5, tzinfo=UTC)
    value = {
        "attemptId": guard.ATTEMPT_ID, "attemptCount": 2,
        "operationKey": guard.OPERATION_KEY, "idempotencyKey": guard.IDEMPOTENCY_KEY,
        "requestHash": guard.REQUEST_HASH, "terminalReason": None, "terminalErrorType": None,
        "installationId": guard.successor.AZ_ID, "generation": guard.successor.AZ_GENERATION,
        "operationKind": "recoverable_store", "state": "running", "revision": 2,
        "acceptedAt": observed - timedelta(seconds=120), "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10), "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed, "controlSecondsRemaining": 18000, "controlExpired": False,
        "definitionRevision": 81, "definitionState": "enabled", "recoveryRevision": 26,
        "manifestHash": guard.recovery.MANIFEST, "members": 12, "runningRuns": 12,
        "succeededRuns": 0, "failedRuns": 0, "datasetReceipts": 12, "relationships": 1,
        "linkCommands": 1, "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0, "routes": 9,
        "liveResources": 3, "devOrgCanary": 0,
    }
    value.update(changes)
    value["attemptHistory"] = changes.get("attemptHistory", [
        {"attempt_id": guard.ORIGINAL_ATTEMPT_ID,
         "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":1",
         "request_hash": guard.REQUEST_HASH, "state": "failed",
         "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
         "terminal_error_type": "IngressJournalConflict"},
        {"attempt_id": value["attemptId"], "idempotency_key": value["idempotencyKey"],
         "request_hash": value["requestHash"], "state": value["state"],
         "terminal_reason_code": value["terminalReason"],
         "terminal_error_type": value["terminalErrorType"]},
    ])
    return value


def test_running_and_elapsed_paths_are_observation_only():
    assert guard.classify(facts())["outcome"] == "RUNNING_HEALTHY_NO_ACTION"
    assert guard.classify(facts(heartbeatAt=None))["outcome"] == "RUNNING_STALE_DIAGNOSE_ONLY"
    result = guard.classify(facts(attemptElapsedSeconds=1801))
    assert result["outcome"] == "RUNNING_HEARTBEAT_ONLY_DIAGNOSE"
    assert result["automaticAction"] is False


def test_success_requires_strict_closure():
    result = guard.classify(facts(state="succeeded", runningRuns=0, succeededRuns=12,
        retirements=1, linkStoreReceipts=1, ecomLinks=1168, linkOutbox=1168))
    assert result["outcome"] == "SUCCEEDED_STRICT_CLOSURE"
    with pytest.raises(RuntimeError, match="AZ guard authority differs"):
        guard.classify(facts(state="succeeded", runningRuns=0, succeededRuns=12))


def test_failed_and_abandoned_freeze_and_never_execute():
    failed = guard.classify(facts(state="failed",
        terminalReason="RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
        terminalErrorType="IngressJournalConflict"))
    assert failed == {"outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}
    abandoned = guard.classify(facts(state="abandoned",
        terminalReason="ATTEMPT_LEASE_EXPIRED", terminalErrorType=None))
    assert abandoned == {"outcome": "ABANDONED_FREEZE_BOUNDARY", "automaticAction": False}


@pytest.mark.parametrize(("field", "value"), (("attemptCount", 1), ("attemptId", "wrong"),
    ("definitionRevision", 80), ("recoveryRevision", 25), ("datasetReceipts", 11),
    ("routes", 8), ("devOrgCanary", 1)))
def test_identity_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="AZ guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_script_is_select_only_and_has_no_business_action():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition|register_successor)\b", re.I)
    assert forbidden.search(source) is None
    assert "consumer_connection" in source and "SELECT" in source
