from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ay_successor_cutover.py"


def test_ay_cutover_is_fixed_to_group152_and_one_operation():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "98a056c1-bba0-4073-bda1-0fa16d214f10"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 152" in source
    assert "externalEffectsAllowed" not in source
    assert "run_definition" not in source
