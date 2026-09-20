from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bg_successor_business.py"


def test_bg_successor_uses_exact_bf_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"' in source
    assert 'successor.AV_GENERATION = "477c3f92-06f0-4dae-9445-ce6d09c3f462"' in source
    assert 'successor.AU_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"' in source
    assert 'successor.DETACH = "03852ebe-20e0-4a41-a5fc-c9eb3aa927dd"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 146' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 173' in source
    assert "run_definition" not in source
