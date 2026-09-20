from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_successor_business.py"


def test_bl_successor_uses_exact_bk_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"' in source
    assert 'successor.AV_GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"' in source
    assert 'successor.AU_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"' in source
    assert 'successor.DETACH = "dfce56ec-4bff-4793-a5d5-dab4ad45aa1c"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 161' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 188' in source
    assert "run_definition" not in source
