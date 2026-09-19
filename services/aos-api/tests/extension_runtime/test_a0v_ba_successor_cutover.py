from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_successor_cutover.py"


def test_ba_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "c9f78abb-2df1-450e-be02-11ae0bcc7fcf"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 155' in source
    assert 'a0v-qyh-clean-generation-ba-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
