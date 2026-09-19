from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bc_successor_cutover.py"


def test_bc_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "a2c78a81-eb53-4b13-b390-2b029530313f"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 161' in source
    assert 'a0v-qyh-clean-generation-bc-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
