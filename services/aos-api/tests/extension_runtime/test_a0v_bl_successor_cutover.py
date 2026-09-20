from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_successor_cutover.py"


def test_bl_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "7acaa1be-bfe3-481b-9841-c4b09779b4f8"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 188' in source
    assert 'a0v-qyh-clean-generation-bl-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
