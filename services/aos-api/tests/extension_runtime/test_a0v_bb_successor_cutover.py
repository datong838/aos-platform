from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bb_successor_cutover.py"


def test_bb_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "8542118b-56fb-48f5-852f-5a933a38bdee"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 158' in source
    assert 'a0v-qyh-clean-generation-bb-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
