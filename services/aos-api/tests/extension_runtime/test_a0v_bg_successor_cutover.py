from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bg_successor_cutover.py"


def test_bg_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "a7928a35-652a-4eaf-8858-d6d86ba7cabe"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 173' in source
    assert 'a0v-qyh-clean-generation-bg-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
