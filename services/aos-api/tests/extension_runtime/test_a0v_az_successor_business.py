from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_az_successor_business.py"


def test_az_successor_locks_identity_and_ax_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"' in source
    assert 'successor.AV_GENERATION = "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"' in source
    assert 'successor.DETACH = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 125" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 152" in source
    assert "run_definition" not in source
