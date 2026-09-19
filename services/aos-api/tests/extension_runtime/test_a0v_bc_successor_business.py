from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bc_successor_business.py"


def test_bc_successor_uses_exact_bb_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "3b895c30-34ca-4710-b978-02645d49c83a"' in source
    assert 'successor.AV_GENERATION = "31776dcd-e28f-4b6d-ae45-75fb0ab5a505"' in source
    assert 'successor.AU_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"' in source
    assert 'successor.DETACH = "0dd16596-c66b-4390-b9dc-0504c1a822c7"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 134' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 161' in source
    assert "run_definition" not in source
