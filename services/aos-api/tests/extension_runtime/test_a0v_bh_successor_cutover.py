from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bh_successor_cutover.py"


def test_bh_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "d21dc573-c75f-47cc-8c9a-e9d2545d5f17"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 176' in source
    assert 'a0v-qyh-clean-generation-bh-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
