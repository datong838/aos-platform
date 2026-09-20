from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bg_saved_snapshot_recovery.py"


def test_bg_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 100" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 101" in source
    assert "recovery.RECOVERY_REVISION = 33" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 102" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 103" in source
    assert "recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bf-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
