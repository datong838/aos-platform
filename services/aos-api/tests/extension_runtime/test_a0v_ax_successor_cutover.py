from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ax_successor_cutover.py"


def test_ax_cutover_is_fixed_to_group149_and_one_operation():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "900ed51b-9c97-424b-9a19-5e4dc2868f66"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 149" in source
    assert "externalEffectsAllowed" not in source
    assert "run_definition" not in source
