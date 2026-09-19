from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_saved_snapshot_recovery.py"


def test_bf_saved_recovery_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 97" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 98" in source
    assert "recovery.RECOVERY_REVISION = 32" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 99" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 100" in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "be-saved-snapshot-recovery-v1"' in source
    assert "run_definition" not in source
