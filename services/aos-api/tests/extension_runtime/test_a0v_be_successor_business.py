from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_be_successor_business.py"


def test_be_successor_uses_exact_bd_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"' in source
    assert 'successor.AV_GENERATION = "93349d9b-ad61-4919-9cbd-e1e9b02545bb"' in source
    assert 'successor.AU_ID = "c2d6ef97-30ec-4980-9421-54a899607853"' in source
    assert 'successor.DETACH = "c896fec3-dbe2-46fe-be60-3cc249b4b4ed"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 140' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 167' in source
    assert "run_definition" not in source
