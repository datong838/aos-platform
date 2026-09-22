"""The W expiry executor uses existing Owners and preserves snapshot history."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_w_expired_retirement.py'
SPEC=importlib.util.spec_from_file_location('a0v_w_expired_retirement',PATH)
retirement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retirement)


def test_exact_w_generation_and_transferred_definition_are_fixed():
    assert retirement.W_ID=='79e7c90d-4e3a-43e0-a0ae-b81d75c11e8c'
    assert retirement.GENERATION=='b4426dfd-a459-41ad-b1e8-fdc440f788db'
    source=PATH.read_text(encoding='utf-8')
    assert '{"revision": 8, "state": "disabled"}' in source
    assert 'runtime_pending' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source=PATH.read_text(encoding='utf-8')
    assert 'service.request(' in source and 'RuntimeDisableConsumer' in source
    assert 'finish_claimed' in source
    assert 'UPDATE meta_schedule_run' not in source
    assert 'pipeline_snapshot_group_input' not in source
