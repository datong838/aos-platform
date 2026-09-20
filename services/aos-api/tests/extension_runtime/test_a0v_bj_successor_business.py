from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bj_successor_business.py"


def test_bj_successor_uses_exact_bi_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"' in source
    assert 'successor.AV_GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"' in source
    assert 'successor.AU_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"' in source
    assert 'successor.DETACH = "64375b18-389a-4e5b-bd17-c7e03a63edd6"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 155' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 182' in source
    assert "run_definition" not in source
