"""AQ transfers the frozen group without source rereads or manual execution."""
import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aq_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_aq_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_aq_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AQ_ID == "d6839bf3-55b5-474c-aa21-49966e15db3d"
    assert recovery.successor.AQ_GENERATION == "b31be2a7-36fd-4348-9ff8-10939cc3d1cd"
    assert 'replacement.load("create-aq")' in source
    assert 'current["body"]["installationId"] != successor.AP_ID' in source
    assert 'current["body"]["revision"] != 63' in source
    assert '"ap-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-aq-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 64' in source
    assert 'idempotency_key="a0v-aq-saved-input-recovery-v21"' in source
    assert 'get("revision") != 21' in source
    assert 'get("revision") != 65' in source
    assert recovery.ACTIONS == (
        "prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "pause-failed", "disable"
    )
    assert recovery.ATTEMPT_ID == "16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82"
    assert "AQ_SAVED_SNAPSHOT_FAILED_RECOVERY_PAUSED" in source
    assert "a0v-aq-saved-snapshot-pause-failed-v1" in source
    assert '"linkStoreReceipts": 0' in source
    assert '"ecomLinks": 0' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source
