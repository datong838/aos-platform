from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_terminal_pause_recovery.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_bl_terminal_pause_recovery", SCRIPT)
pause = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pause)


def facts(**changes):
    observed = datetime(2026, 9, 20, 7, 48, tzinfo=UTC)
    value = {
        "attemptId": pause.guard.ATTEMPT_ID, "attemptCount": 1,
        "operationKey": pause.guard.OPERATION_KEY, "idempotencyKey": pause.guard.IDEMPOTENCY_KEY,
        "requestHash": pause.guard.REQUEST_HASH,
        "installationId": pause.guard.successor.BL_ID,
        "generation": pause.guard.successor.BL_GENERATION,
        "operationKind": "recoverable_store", "state": "abandoned", "revision": 46,
        "acceptedAt": observed - timedelta(seconds=1820), "attemptElapsedSeconds": 1820,
        "heartbeatAt": observed - timedelta(seconds=500), "leaseUntil": observed - timedelta(seconds=380),
        "observedAt": observed, "controlSecondsRemaining": 19000, "controlExpired": False,
        "terminalReason": "ATTEMPT_LEASE_EXPIRED", "terminalErrorType": None,
        "definitionRevision": 117, "definitionState": "enabled", "recoveryRevision": 38,
        "manifestHash": pause.guard.recovery.MANIFEST, "members": 12, "runningRuns": 12,
        "succeededRuns": 0, "failedRuns": 0, "datasetReceipts": 12, "relationships": 1,
        "linkCommands": 1, "linkCount": 1168, "retirements": 0, "linkStoreReceipts": 0,
        "ecomLinks": 0, "linkOutbox": 0, "projectionPending": 0, "routes": 9,
        "liveResources": 3, "devOrgCanary": 0,
    }
    value.update(changes)
    return value


PROCESSES = {"runtimeHost": 0, "snapshotWorker": 0, "supervisor": 0}


def test_exact_terminal_boundary_is_green():
    assert pause.classify(facts(), PROCESSES)["outcome"].endswith("PREFLIGHT_GREEN")


@pytest.mark.parametrize(("field", "value"), (("revision", 45), ("attemptCount", 2),
    ("terminalReason", "unexpected"), ("linkStoreReceipts", 1)))
def test_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError):
        pause.classify(facts(**{field: value}), PROCESSES)


def test_stop_only_owner_and_no_resend():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "controls=None" in source
    assert "intent=\"disable\"" in source
    assert "run_definition" not in source
