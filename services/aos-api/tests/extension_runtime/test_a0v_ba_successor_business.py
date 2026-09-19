from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_successor_business.py"


def test_ba_successor_uses_exact_az_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"' in source
    assert 'successor.AV_GENERATION = "197f5036-656a-4b58-a261-e93e2fffea18"' in source
    assert 'successor.AU_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"' in source
    assert 'successor.DETACH = "ee221609-d3d5-4227-8382-063d2ca0eab2"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 128' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 155' in source
    assert "run_definition" not in source
