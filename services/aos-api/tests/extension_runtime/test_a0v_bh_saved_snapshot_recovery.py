from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bh_saved_snapshot_recovery.py"


def test_bh_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 103" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 104" in source
    assert "recovery.RECOVERY_REVISION = 34" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 105" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 106" in source
    assert "recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bg-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
