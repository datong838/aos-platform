"""AS guard observes one natural attempt and never executes business work."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_as_attempt_guard.py"
import sys
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("a0v_as_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 6, 38, tzinfo=UTC)
    value = {
        "attemptId": guard.ATTEMPT_ID, "attemptCount": 1,
        "operationKey": guard.OPERATION_KEY, "idempotencyKey": guard.BASE_IDEMPOTENCY_KEY + ":1",
        "requestHash": guard.REQUEST_HASH, "terminalReason": None, "terminalErrorType": None,
        "installationId": guard.successor.AS_ID, "generation": guard.successor.AS_GENERATION,
        "operationKind": "recoverable_store", "state": "running", "revision": 2,
        "acceptedAt": observed - timedelta(seconds=120), "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10), "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed, "controlSecondsRemaining": 18000, "controlExpired": False,
        "definitionRevision": 69, "definitionState": "enabled", "recoveryRevision": 22,
        "manifestHash": guard.recovery.MANIFEST, "members": 12, "runningRuns": 12,
        "succeededRuns": 0, "failedRuns": 0, "datasetReceipts": 12, "relationships": 1,
        "linkCommands": 1, "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0, "routes": 9,
        "liveResources": 3, "devOrgCanary": 0,
    }
    value.update(changes)
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
    with pytest.raises(RuntimeError, match="AS guard authority differs"):
        guard.classify(facts(state="succeeded", runningRuns=0, succeededRuns=12))


def test_failed_and_abandoned_never_execute():
    assert guard.classify(facts(state="failed",
        terminalReason="RECOVERABLE_INGRESS_CANCELLED",
        terminalErrorType="IngressJournalConflict")) == {
        "outcome": "FAILED_FREEZE_BOUNDARY", "automaticAction": False}
    with pytest.raises(RuntimeError, match="AS guard authority differs"):
        guard.classify(facts(state="failed", terminalReason="different",
                             terminalErrorType="IngressJournalConflict"))
    with pytest.raises(RuntimeError, match="AS guard authority differs"):
        guard.classify(facts(state="failed",
            terminalReason="RECOVERABLE_INGRESS_CANCELLED",
            terminalErrorType="IngressJournalConflict", ecomLinks=1))
    assert guard.classify(facts(state="abandoned", terminalReason="ATTEMPT_LEASE_EXPIRED")) == {
        "outcome": "ABANDONED_WAIT_NATURAL_SUCCESSOR", "automaticAction": False}


@pytest.mark.parametrize(("field", "value"), (("attemptCount", 2), ("attemptId", "wrong"),
    ("definitionRevision", 68), ("recoveryRevision", 21), ("datasetReceipts", 11),
    ("routes", 8), ("devOrgCanary", 1)))
def test_identity_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="AS guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_script_is_select_only_and_has_no_business_action():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition|register_successor)\b", re.I)
    assert forbidden.search(source) is None
    assert "consumer_connection" in source and "SELECT" in source
