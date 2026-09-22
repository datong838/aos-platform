"""AF expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_af_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_af_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_af_generation_and_disabled_definition_are_fixed():
    assert retirement.AF_ID == "0bf928a9-877a-4b97-9778-7f678d6cd7d4"
    assert retirement.GENERATION == "173e267c-f031-4fda-b801-bc9e0a0d2264"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 33, "state": "disabled"}' in source
    assert 'row["revision"] != 69' in source
    assert 'row["cutover_group_revision"] != 96' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
