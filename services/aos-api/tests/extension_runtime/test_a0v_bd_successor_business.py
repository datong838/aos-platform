from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_successor_business.py"


def test_bd_successor_uses_exact_bc_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "c2d6ef97-30ec-4980-9421-54a899607853"' in source
    assert 'successor.AV_GENERATION = "f5e01f1d-e6c5-425a-9145-6f7a82ec65e5"' in source
    assert 'successor.AU_ID = "3b895c30-34ca-4710-b978-02645d49c83a"' in source
    assert 'successor.DETACH = "39bb3f98-78b6-444b-9d5c-a51991b03f42"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 137' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 164' in source
    assert "run_definition" not in source
