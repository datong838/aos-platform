from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_successor_cutover.py"


def test_bf_cutover_is_exact_and_serial():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "fba548a4-b69d-4ce2-abfc-65abfac41147"' in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 170' in source
    assert 'a0v-qyh-clean-generation-bf-cutover-v1' in source
    assert '"approve", "prepare", "pause", "commit", "validate", "resume", "inspect"' in source
    assert "run_definition" not in source
