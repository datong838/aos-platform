from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bc_saved_snapshot_recovery.py"


def test_bc_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 88" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 89" in source
    assert "recovery.RECOVERY_REVISION = 29" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 90" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 91" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bb-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
