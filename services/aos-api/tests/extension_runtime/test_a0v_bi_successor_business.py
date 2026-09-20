from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bi_successor_business.py"


def test_bi_successor_uses_exact_bh_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"' in source
    assert 'successor.AV_GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"' in source
    assert 'successor.AU_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"' in source
    assert 'successor.DETACH = "8609e798-2f61-43df-9838-cad7da02c230"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 152' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 179' in source
    assert "run_definition" not in source
