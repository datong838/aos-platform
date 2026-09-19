from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ax_successor_business.py"


def test_ax_successor_locks_signed_identity_and_aw_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"' in source
    assert 'successor.AV_GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"' in source
    assert 'successor.DETACH = "0c50775b-62fe-4251-81f4-3c9a8709a90e"' in source
    assert "successor.PREDECESSOR_BINDING_REVISION = 11" in source
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 6" in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 122" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 149" in source
    assert "run_definition" not in source
