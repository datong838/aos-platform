"""AA expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aa_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_aa_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_aa_generation_and_disabled_definition_are_fixed():
    assert retirement.AA_ID == "d0476259-7e04-4cf6-ba94-9d7da1c73db0"
    assert retirement.GENERATION == "44236c8a-cf56-451c-b620-21c63e48d87e"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 18, "state": "disabled"}' in source
    assert 'row["revision"] != 54' in source
    assert 'row["cutover_group_revision"] != 81' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
