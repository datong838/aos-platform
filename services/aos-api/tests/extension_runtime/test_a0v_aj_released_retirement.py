"""AJ release uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aj_released_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_aj_released_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_aj_generation_and_disabled_definition_are_fixed():
    assert retirement.AJ_ID == "cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244"
    assert retirement.GENERATION == "6dc4f34a-5cc6-4b20-bfb8-8a002a7dcd76"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 45, "state": "disabled"}' in source
    assert 'row["revision"] != 81' in source
    assert 'row["cutover_group_revision"] != 108' in source
    assert 'row["revision"] != 83' in source
    assert 'row["cutover_group_revision"] != 110' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
