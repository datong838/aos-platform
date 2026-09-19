from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_az_successor_cutover.py"


def test_az_cutover_is_fixed_to_group152_and_one_operation():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "f411835c-ea85-4996-9c64-715e9d04fc35"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 152" in source
    assert "externalEffectsAllowed" not in source
    assert "run_definition" not in source
