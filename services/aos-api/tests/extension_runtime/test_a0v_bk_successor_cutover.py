from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_successor_cutover.py"


def test_bk_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "30355379-f48e-4261-91cc-533f13c34ab6"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 185' in source
    assert 'a0v-qyh-clean-generation-bk-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
