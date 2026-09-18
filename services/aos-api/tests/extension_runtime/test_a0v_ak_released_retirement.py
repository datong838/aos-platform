"""AK release uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ak_released_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ak_released_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ak_generation_and_disabled_definition_are_fixed():
    assert retirement.AK_ID == "038bd251-e2e3-415d-8706-955de809b4df"
    assert retirement.GENERATION == "f2c32bd6-699e-4c06-9dee-074e470d20e0"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 48, "state": "disabled"}' in source
    assert 'row["revision"] != 84' in source
    assert 'row["cutover_group_revision"] != 111' in source
    assert 'row["revision"] != 86' in source
    assert 'row["cutover_group_revision"] != 113' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
