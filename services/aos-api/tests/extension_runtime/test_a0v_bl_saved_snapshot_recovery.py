from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_saved_snapshot_recovery.py"


def test_bl_saved_snapshot_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 115" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 116" in source
    assert "recovery.RECOVERY_REVISION = 38" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 117" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 118" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bk-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
