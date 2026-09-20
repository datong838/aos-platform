from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_saved_snapshot_recovery.py"


def test_bk_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 112" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 113" in source
    assert "recovery.RECOVERY_REVISION = 37" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 114" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 115" in source
    assert "recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bj-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
