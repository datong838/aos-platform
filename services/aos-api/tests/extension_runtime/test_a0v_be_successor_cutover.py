from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_be_successor_cutover.py"


def test_be_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "7bd8c758-35a8-47ab-8498-22129a474fc7"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 167' in source
    assert 'a0v-qyh-clean-generation-be-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
