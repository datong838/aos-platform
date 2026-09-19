"""BF guard fixes one natural attempt and inherits strict closure checks."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_attempt_guard.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_bf_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 23, 20, tzinfo=UTC)
    value = {
        "attemptId": guard.ATTEMPT_ID, "attemptCount": 2,
        "operationKey": guard.OPERATION_KEY, "idempotencyKey": guard.IDEMPOTENCY_KEY,
        "requestHash": guard.REQUEST_HASH, "terminalReason": "RECOVERABLE_INGRESS_CANCELLED",
        "terminalErrorType": "IngressJournalConflict",
        "installationId": guard.successor.BF_ID, "generation": guard.successor.BF_GENERATION,
        "operationKind": "recoverable_store", "state": "failed", "revision": 10,
        "acceptedAt": observed - timedelta(seconds=120), "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10), "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed, "controlSecondsRemaining": 18000, "controlExpired": False,
        "definitionRevision": 99, "definitionState": "enabled", "recoveryRevision": 32,
        "manifestHash": guard.recovery.MANIFEST, "members": 12, "runningRuns": 12,
        "succeededRuns": 0, "failedRuns": 0, "datasetReceipts": 12, "relationships": 1,
        "linkCommands": 1, "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0, "routes": 9,
        "liveResources": 3, "devOrgCanary": 0,
        "attemptHistory": [
            {"attempt_id": guard.ORIGINAL_ATTEMPT_ID,
             "idempotency_key": guard.BASE_IDEMPOTENCY_KEY + ":1",
             "request_hash": guard.REQUEST_HASH, "state": "failed",
             "terminal_reason_code": "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
             "terminal_error_type": "IngressJournalConflict"},
            {"attempt_id": guard.ATTEMPT_ID, "idempotency_key": guard.IDEMPOTENCY_KEY,
             "request_hash": guard.REQUEST_HASH, "state": "failed",
             "terminal_reason_code": "RECOVERABLE_INGRESS_CANCELLED",
             "terminal_error_type": "IngressJournalConflict"},
        ],
    }
    value.update(changes)
    return value


def test_exact_two_failed_attempts_freeze_boundary():
    assert guard.classify(facts())["outcome"] == "FAILED_FREEZE_BOUNDARY"


@pytest.mark.parametrize(("field", "value"), (("attemptCount", 1), ("attemptId", "wrong"),
    ("definitionRevision", 98), ("recoveryRevision", 31), ("routes", 8)))
def test_identity_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="BF guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_script_is_select_only():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition)\b", re.I)
    assert forbidden.search(source) is None
    assert "consumer_connection" in source and "SELECT" in source
