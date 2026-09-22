"""AC expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ac_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ac_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ac_generation_and_disabled_definition_are_fixed():
    assert retirement.AC_ID == "4fbd0873-dede-4c3c-9db8-29c3e14c2c48"
    assert retirement.GENERATION == "cdfa92eb-a695-46e7-9ed4-35a296321403"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 24, "state": "disabled"}' in source
    assert 'row["revision"] != 60' in source
    assert 'row["cutover_group_revision"] != 87' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
