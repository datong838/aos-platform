"""BA guard fixes one natural attempt and never executes business work."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_attempt_guard.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_ba_attempt_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def facts(**changes):
    observed = datetime(2026, 9, 19, 15, 12, tzinfo=UTC)
    value = {
        "attemptId": guard.ATTEMPT_ID, "attemptCount": 1,
        "operationKey": guard.OPERATION_KEY, "idempotencyKey": guard.IDEMPOTENCY_KEY,
        "requestHash": guard.REQUEST_HASH, "terminalReason": None, "terminalErrorType": None,
        "installationId": guard.successor.BA_ID, "generation": guard.successor.BA_GENERATION,
        "operationKind": "recoverable_store", "state": "running", "revision": 2,
        "acceptedAt": observed - timedelta(seconds=120), "attemptElapsedSeconds": 120,
        "heartbeatAt": observed - timedelta(seconds=10), "leaseUntil": observed + timedelta(seconds=110),
        "observedAt": observed, "controlSecondsRemaining": 18000, "controlExpired": False,
        "definitionRevision": 84, "definitionState": "enabled", "recoveryRevision": 27,
        "manifestHash": guard.recovery.MANIFEST, "members": 12, "runningRuns": 12,
        "succeededRuns": 0, "failedRuns": 0, "datasetReceipts": 12, "relationships": 1,
        "linkCommands": 1, "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0, "routes": 9,
        "liveResources": 3, "devOrgCanary": 0,
    }
    value.update(changes)
    return value


def test_running_success_and_terminal_boundaries():
    assert guard.classify(facts())["outcome"] == "RUNNING_HEALTHY_NO_ACTION"
    assert guard.classify(facts(heartbeatAt=None))["outcome"] == "RUNNING_STALE_DIAGNOSE_ONLY"
    success = facts(state="succeeded", runningRuns=0, succeededRuns=12,
        retirements=1, linkStoreReceipts=1, ecomLinks=1168, linkOutbox=1168)
    assert guard.classify(success)["outcome"] == "SUCCEEDED_STRICT_CLOSURE"
    failed = facts(state="failed", terminalReason="RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
                   terminalErrorType="IngressJournalConflict")
    assert guard.classify(failed)["outcome"] == "FAILED_FREEZE_BOUNDARY"


@pytest.mark.parametrize(("field", "value"), (("attemptCount", 2), ("attemptId", "wrong"),
    ("definitionRevision", 83), ("recoveryRevision", 26), ("routes", 8), ("devOrgCanary", 1)))
def test_identity_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError, match="BA guard authority differs"):
        guard.classify(facts(**{field: value}))


def test_script_is_select_only():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition)\b", re.I)
    assert forbidden.search(source) is None
    assert "consumer_connection" in source and "SELECT" in source
