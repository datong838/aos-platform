from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_successor_business.py"


def test_bf_successor_uses_exact_be_detach_and_new_identity():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"' in source
    assert 'successor.AV_GENERATION = "e33e0a9e-7296-4374-9aa9-113f1ed79b5f"' in source
    assert 'successor.AU_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"' in source
    assert 'successor.DETACH = "2b758ca2-8afd-48a4-af23-6367fe505758"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 143' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 170' in source
    assert "run_definition" not in source
