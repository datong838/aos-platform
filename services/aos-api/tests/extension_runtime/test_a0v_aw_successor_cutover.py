from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aw_successor_cutover.py"


def test_aw_cutover_is_exact_and_no_effect():
    import a0v_aw_successor_business as successor

    assert successor.AV_ID == successor.AW_ID
    assert successor.AV_GENERATION == successor.AW_GENERATION
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "255d4a17-0ec9-4506-a1a9-f3337103f832"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 146" in source
    assert "a0v-qyh-clean-generation-aw-cutover-v1" in source
    base = (ROOT / "scripts/a0v_av_successor_cutover.py").read_text(encoding="utf-8")
    assert '"externalEffectsAllowed": False' in base
    assert "PREDECESSOR_GROUP_REVISION = 143" in base
    assert "run_definition" not in source and "run_definition" not in base
