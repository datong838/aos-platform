from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bj_successor_cutover.py"


def test_bj_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "337aa516-42f1-47fc-afb7-980d3c0e62e1"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 182' in source
    assert 'a0v-qyh-clean-generation-bj-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
