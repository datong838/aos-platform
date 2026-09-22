"""AE expiry uses existing disable Owners and preserves saved snapshot input."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ae_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ae_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ae_generation_and_disabled_definition_are_fixed():
    assert retirement.AE_ID == "d02f90f2-eb0e-4859-ad58-35b17ddbcd6a"
    assert retirement.GENERATION == "36a57887-4f28-45e7-8515-2d94a343b5ed"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 30, "state": "disabled"}' in source
    assert 'row["revision"] != 66' in source
    assert 'row["cutover_group_revision"] != 93' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
