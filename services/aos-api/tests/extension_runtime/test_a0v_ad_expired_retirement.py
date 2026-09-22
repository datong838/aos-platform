"""AD expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ad_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ad_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ad_generation_and_disabled_definition_are_fixed():
    assert retirement.AD_ID == "42d9f8bd-11b0-4f8d-8c4d-75458ab23c94"
    assert retirement.GENERATION == "7a2f5483-8ff6-4672-b174-f273885e99d0"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 27, "state": "disabled"}' in source
    assert 'row["revision"] != 63' in source
    assert 'row["cutover_group_revision"] != 90' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
