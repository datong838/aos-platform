"""AG expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ag_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ag_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ag_generation_and_disabled_definition_are_fixed():
    assert retirement.AG_ID == "37d36900-5b9a-4cd0-9108-4ef5ded25d58"
    assert retirement.GENERATION == "31192641-3558-4cf2-9ad9-ea2375c69900"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 36, "state": "disabled"}' in source
    assert 'row["revision"] != 72' in source
    assert 'row["cutover_group_revision"] != 99' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
