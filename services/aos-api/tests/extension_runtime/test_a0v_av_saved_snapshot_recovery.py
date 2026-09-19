import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_av_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_av_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_av_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AV_ID == "5f01eda8-ca5f-4892-8510-385704ccddb2"
    assert recovery.successor.AV_GENERATION == "17104053-f4c9-47e1-89b0-f3f353076dda"
    assert 'replacement.load("create-av")' in source
    assert recovery.snapshot_predecessor.AT_ID == "631e6d01-a5bb-4865-95eb-07d5665ed957"
    assert 'current["body"]["installationId"] != snapshot_predecessor.AT_ID' in source
    assert 'current["body"]["revision"] != 73' in source
    assert '"at-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-av-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 74' in source
    assert 'idempotency_key="a0v-av-saved-input-recovery-v24"' in source
    assert 'get("revision") != 24' in source
    assert 'get("revision") != 75' in source
    assert recovery.ACTIONS == (
        "prepare", "schedule-ingest", "controls", "transfer", "renew", "enable",
        "inspect", "pause-terminal", "disable",
    )
    assert '"sourceReads": 0' in source
    assert "def pause_failed" not in source
    assert "AV_SAVED_SNAPSHOT_TERMINAL_RECOVERY_PAUSED" in source
    assert "a0v-av-saved-snapshot-pause-terminal-v1" in source
    assert '"attemptCount": 1' in source
    assert "run_definition" not in source
    assert 'a0v-at-saved-snapshot-pause-failed-v1' not in source
