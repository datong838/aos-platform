from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_expired_attempt_recovery.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_bl_expired_attempt_recovery", SCRIPT)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def facts(**changes):
    observed = datetime(2026, 9, 20, 7, 48, tzinfo=UTC)
    value = {
        "attemptId": recovery.guard.ATTEMPT_ID, "attemptCount": 1,
        "installationId": recovery.guard.successor.BL_ID,
        "generation": recovery.guard.successor.BL_GENERATION,
        "state": "running", "revision": 45,
        "attemptElapsedSeconds": 1820,
        "leaseUntil": observed - timedelta(seconds=300), "observedAt": observed,
        "definitionRevision": 117, "definitionState": "enabled", "recoveryRevision": 38,
        "routes": 9, "runningRuns": 12, "datasetReceipts": 12,
        "linkStoreReceipts": 0, "ecomLinks": 0, "projectionPending": 0,
        "succeededRuns": 0, "failedRuns": 0, "devOrgCanary": 0,
    }
    value.update(changes)
    return value


PROCESSES = {"runtimeHost": 0, "snapshotWorker": 0, "supervisor": 0}


def test_exact_expired_boundary_is_green():
    assert recovery.classify(facts(), PROCESSES)["outcome"].endswith("PREFLIGHT_GREEN")


@pytest.mark.parametrize(("field", "value"), (("attemptCount", 2), ("revision", 44),
    ("attemptElapsedSeconds", 1799), ("linkStoreReceipts", 1), ("routes", 8)))
def test_drift_fails_closed(field, value):
    with pytest.raises(RuntimeError):
        recovery.classify(facts(**{field: value}), PROCESSES)


def test_live_process_fails_closed():
    with pytest.raises(RuntimeError, match="process boundary"):
        recovery.classify(facts(), PROCESSES | {"runtimeHost": 1})


def test_uses_existing_owner_without_business_resend():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ExpiredSignedReadAttemptRecovery" in source
    assert "run_definition" not in source
    assert "sourceReads\": 0" in source
