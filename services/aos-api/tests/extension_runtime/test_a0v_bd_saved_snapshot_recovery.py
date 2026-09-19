from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_saved_snapshot_recovery.py"


def test_bd_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "3b895c30-34ca-4710-b978-02645d49c83a"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 91" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 92" in source
    assert "recovery.RECOVERY_REVISION = 30" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 93" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 94" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bc-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
