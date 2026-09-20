from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bj_saved_snapshot_recovery.py"


def test_bj_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 109" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 110" in source
    assert "recovery.RECOVERY_REVISION = 36" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 111" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 112" in source
    assert "recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bi-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
