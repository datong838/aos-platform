from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bi_saved_snapshot_recovery.py"


def test_bi_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 106" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 107" in source
    assert "recovery.RECOVERY_REVISION = 35" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 108" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 109" in source
    assert "recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT = 1" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bh-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
