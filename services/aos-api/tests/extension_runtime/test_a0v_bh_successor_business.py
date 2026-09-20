from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bh_successor_business.py"


def test_bh_successor_uses_exact_bg_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"' in source
    assert 'successor.AV_GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"' in source
    assert 'successor.AU_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"' in source
    assert 'successor.DETACH = "48e4d856-6652-4903-af9f-49bf4774bc0d"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 149' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 176' in source
    assert "run_definition" not in source
