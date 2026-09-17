"""AH expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ah_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ah_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ah_generation_and_disabled_definition_are_fixed():
    assert retirement.AH_ID == "9fe97ea8-275a-47d0-a0f1-d2064a8d62c6"
    assert retirement.GENERATION == "f2d43d1d-af4e-477d-afd3-4f1174404734"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 39, "state": "disabled"}' in source
    assert 'row["revision"] != 75' in source
    assert 'row["cutover_group_revision"] != 102' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
