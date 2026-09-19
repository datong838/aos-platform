from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_successor_cutover.py"


def test_bd_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "e4baf529-cc27-4a0d-aa18-139b22f6dd19"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 164' in source
    assert 'a0v-qyh-clean-generation-bd-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
