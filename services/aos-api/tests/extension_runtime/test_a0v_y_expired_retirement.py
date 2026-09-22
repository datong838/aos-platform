"""The Y expiry executor uses existing Owners and preserves snapshot history."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_y_expired_retirement.py'
SPEC=importlib.util.spec_from_file_location('a0v_y_expired_retirement',PATH)
retirement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retirement)


def test_exact_y_generation_and_transferred_definition_are_fixed():
    assert retirement.Y_ID=='c76d26b9-8a93-4476-a6fe-206e10930bc9'
    assert retirement.GENERATION=='87cd4104-999d-4224-b1ee-772b22a05445'
    source=PATH.read_text(encoding='utf-8')
    assert '{"revision": 14, "state": "disabled"}' in source
    assert 'runtime_pending' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source=PATH.read_text(encoding='utf-8')
    assert 'service.request(' in source and 'RuntimeDisableConsumer' in source
    assert 'finish_claimed' in source
    assert 'UPDATE meta_schedule_run' not in source
    assert 'pipeline_snapshot_group_input' not in source
