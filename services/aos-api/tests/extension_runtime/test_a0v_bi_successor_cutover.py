from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bi_successor_cutover.py"


def test_bi_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "903babc0-58e9-4ae9-b835-6bed4471ba28"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 179' in source
    assert 'a0v-qyh-clean-generation-bi-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
