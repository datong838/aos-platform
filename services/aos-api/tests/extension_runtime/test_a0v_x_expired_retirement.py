"""The X expiry executor uses existing Owners and preserves snapshot history."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_x_expired_retirement.py'
SPEC=importlib.util.spec_from_file_location('a0v_x_expired_retirement',PATH)
retirement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retirement)


def test_exact_x_generation_and_transferred_definition_are_fixed():
    assert retirement.X_ID=='651dcf7c-08c1-4511-ae23-6e5e864f2b68'
    assert retirement.GENERATION=='0663a082-ea85-4110-9730-e13c230cd95c'
    source=PATH.read_text(encoding='utf-8')
    assert '{"revision": 11, "state": "disabled"}' in source
    assert 'runtime_pending' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source=PATH.read_text(encoding='utf-8')
    assert 'service.request(' in source and 'RuntimeDisableConsumer' in source
    assert 'finish_claimed' in source
    assert 'UPDATE meta_schedule_run' not in source
    assert 'pipeline_snapshot_group_input' not in source
