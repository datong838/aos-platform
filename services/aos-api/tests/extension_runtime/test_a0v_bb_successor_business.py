from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bb_successor_business.py"


def test_bb_successor_uses_exact_ba_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"' in source
    assert 'successor.AV_GENERATION = "099c4d17-47fb-4c07-9ef1-c627ca7b4239"' in source
    assert 'successor.AU_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"' in source
    assert 'successor.DETACH = "707b4a88-2823-4368-81c6-5e5525c3ea48"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 131' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 158' in source
    assert "run_definition" not in source
