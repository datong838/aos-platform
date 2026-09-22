"""AB expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ab_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ab_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ab_generation_and_disabled_definition_are_fixed():
    assert retirement.AB_ID == "b57e5f93-f075-45f1-a42c-4340255e4f74"
    assert retirement.GENERATION == "00fba2de-a505-49f1-a3e6-696d7415fc79"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 21, "state": "disabled"}' in source
    assert 'row["revision"] != 57' in source
    assert 'row["cutover_group_revision"] != 84' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
