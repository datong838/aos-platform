"""a0v089 deployment is fixed to one backed-up isolated migration."""
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_runtime_attempt_terminal_reason_deploy.py"


def test_deploy_is_exact_backed_up_and_data_preserving():
    source = PATH.read_text(encoding="utf-8")
    assert "SOURCE, TARGET = 'a0v_088', 'a0v_089'" in source
    assert "'pg_dump'" in source and "'--snapshot'" in source
    assert "if after != before" in source
    assert "command.upgrade(cfg, TARGET)" in source
    assert "'businessWrites': 0" in source and "'sourceReads': 0" in source
