"""The V expiry executor uses existing Owners and preserves snapshot history."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_v_expired_retirement.py'
SPEC=importlib.util.spec_from_file_location('a0v_v_expired_retirement',PATH)
retirement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retirement)


def test_exact_v_generation_and_transferred_definition_are_fixed():
    assert retirement.V_ID=='33a63ef9-405d-4893-b9f8-dd569f64b46b'
    assert retirement.GENERATION=='5a9ce3d0-c4c4-4545-a5c7-d286fdb62ddb'
    source=PATH.read_text(encoding='utf-8')
    assert '{"revision": 5, "state": "disabled"}' in source
    assert 'runtime_pending' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source=PATH.read_text(encoding='utf-8')
    assert 'service.request(' in source and 'RuntimeDisableConsumer' in source
    assert 'finish_claimed' in source
    assert 'UPDATE meta_schedule_run' not in source
    assert 'pipeline_snapshot_group_input' not in source
