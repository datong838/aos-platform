from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bb_saved_snapshot_recovery.py"


def test_bb_saved_recovery_is_exact_and_single_attempt():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 85" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 86" in source
    assert "recovery.RECOVERY_REVISION = 28" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 87" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 88" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "ba-saved-snapshot-recovery-v1"' in source
    assert "recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1" in source
    assert "run_definition" not in source
