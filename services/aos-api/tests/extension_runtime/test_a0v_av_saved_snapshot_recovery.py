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
    successor_source = (PATH.parent / "a0v_av_successor_business.py").read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert 'AV_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"' in successor_source
    assert 'AV_GENERATION = "17104053-f4c9-47e1-89b0-f3f353076dda"' in successor_source
    assert 'replacement.load("create-av")' in source
    assert recovery.snapshot_predecessor.AT_ID == "631e6d01-a5bb-4865-95eb-07d5665ed957"
    assert recovery.PREDECESSOR_INSTALLATION_ID == recovery.snapshot_predecessor.AT_ID
    assert recovery.PREDECESSOR_DEFINITION_REVISION == 73
    assert recovery.PREDECESSOR_RECOVERY_STATE == "at-saved-snapshot-recovery-v1"
    assert recovery.TRANSFER_KEY == "a0v-av-saved-definition-transfer-v1"
    assert recovery.TRANSFERRED_DEFINITION_REVISION == 74
    assert recovery.RENEW_KEY == "a0v-av-saved-input-recovery-v24"
    assert recovery.RECOVERY_REVISION == 24
    assert recovery.ENABLED_DEFINITION_REVISION == 75
    assert recovery.ACTIONS == (
        "prepare", "schedule-ingest", "controls", "transfer", "renew", "enable",
        "inspect", "pause-terminal", "disable",
    )
    assert '"sourceReads": 0' in source
    assert "def pause_failed" not in source
    assert 'INSTALLATION_LABEL = "AV"' in source
    assert recovery.PAUSE_KEY == "a0v-av-saved-snapshot-pause-terminal-v1"
    assert recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT == 1
    assert '"attemptCount": EXPECTED_TERMINAL_ATTEMPT_COUNT' in source
    assert "run_definition" not in source
    assert 'a0v-at-saved-snapshot-pause-failed-v1' not in source
