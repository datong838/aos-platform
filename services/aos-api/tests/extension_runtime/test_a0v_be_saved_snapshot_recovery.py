from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_be_saved_snapshot_recovery.py"


def test_be_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "c2d6ef97-30ec-4980-9421-54a899607853"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 94" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 95" in source
    assert "recovery.RECOVERY_REVISION = 31" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 96" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 97" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bd-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
