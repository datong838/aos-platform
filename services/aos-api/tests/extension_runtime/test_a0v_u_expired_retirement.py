"""The U expiry executor uses existing Owners and preserves snapshot history."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_u_expired_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_u_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_u_generation_and_disabled_definition_are_fixed():
    assert retirement.U_ID == "277fe01c-ece7-4c8f-9500-fc1ba0d5f050"
    assert retirement.GENERATION == "f576ea28-7c2b-4032-8b4c-9d196df6228e"
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": 4, "state": "disabled"}' in source
    assert 'runtime_pending' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "service.request(" in source
    assert "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
    assert "sourceReads" not in source
