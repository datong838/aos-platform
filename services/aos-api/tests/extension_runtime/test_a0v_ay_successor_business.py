from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ay_successor_business.py"


def test_ay_successor_locks_signed_identity_and_ax_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'successor.AV_ID = "81df994f-23ce-4448-ac46-366aaee63924"' in source
    assert 'successor.AV_GENERATION = "a1069f60-46f5-41a8-bd18-61ed677eb3bd"' in source
    assert 'successor.DETACH = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"' in source
    assert "successor.PREDECESSOR_BINDING_REVISION = 8" in source
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 4" in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 125" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 152" in source
    assert "run_definition" not in source
