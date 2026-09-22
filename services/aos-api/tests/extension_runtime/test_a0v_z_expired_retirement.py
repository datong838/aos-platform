"""The Z expiry executor uses existing Owners and preserves snapshot history."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_z_expired_retirement.py'
SPEC=importlib.util.spec_from_file_location('a0v_z_expired_retirement',PATH)
retirement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retirement)


def test_exact_z_generation_and_paused_definition_are_fixed():
    assert retirement.Z_ID=='cd426e3a-f5e8-45a2-b6a8-8991294b467e'
    assert retirement.GENERATION=='d49fe4fd-55c8-4688-9602-5dbff946bc36'
    source=PATH.read_text(encoding='utf-8')
    assert '{"revision": 17, "state": "disabled"}' in source
    assert 'runtime_pending' in source


def test_executor_uses_disable_owner_and_never_changes_snapshot_runs():
    source=PATH.read_text(encoding='utf-8')
    assert 'service.request(' in source and 'RuntimeDisableConsumer' in source
    assert 'finish_claimed' in source
    assert 'UPDATE meta_schedule_run' not in source
    assert 'pipeline_snapshot_group_input' not in source
