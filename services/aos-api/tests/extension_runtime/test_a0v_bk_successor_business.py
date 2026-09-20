from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_successor_business.py"


def test_bk_successor_uses_exact_bj_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"' in source
    assert 'successor.AV_GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"' in source
    assert 'successor.AU_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"' in source
    assert 'successor.DETACH = "2c5d28d5-cfcc-474d-827d-d0031d0de4d8"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 158' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 185' in source
    assert "run_definition" not in source
