"""AI release uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ai_released_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ai_released_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ai_generation_and_disabled_definition_are_fixed():
    assert retirement.AI_ID == "59d91f1c-efd7-4097-8ce0-1d4fa9452c0f"
    assert retirement.GENERATION == "3512c4da-841c-4bd6-a711-343c163b0632"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 42, "state": "disabled"}' in source
    assert 'row["revision"] != 78' in source
    assert 'row["cutover_group_revision"] != 105' in source
    assert 'row["revision"] != 80' in source
    assert 'row["cutover_group_revision"] != 107' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
