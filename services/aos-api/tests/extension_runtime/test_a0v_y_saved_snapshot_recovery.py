"""Y recovery transfers one saved group and never rereads the source."""
import importlib.util
from pathlib import Path
import sys


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_y_saved_snapshot_recovery.py'
sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location('a0v_y_saved_snapshot_recovery',PATH)
recovery=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_y_recovery_uses_new_controls_and_same_saved_group():
    source=PATH.read_text(encoding='utf-8')
    assert recovery.GROUP=='c5ff1926-45b0-56de-b6b3-07d5b7d053a1'
    assert recovery.MANIFEST.startswith('sha256:03cccc')
    assert "snapshot.CONTROL_PREFIX='a0v-y-snapshot'" in source
    assert 'service.transfer_saved_recovery(' in source
    assert 'service.renew_saved_group(' in source
    assert "'sourceReads':0" in source


def test_y_recovery_has_no_direct_run_or_source_mutation():
    source=PATH.read_text(encoding='utf-8')
    assert 'run_definition' not in source
    for mutation in ('INSERT INTO pipeline_snapshot_group_input',
                     'UPDATE pipeline_snapshot_group_input',
                     'DELETE FROM pipeline_snapshot_group_input'):
        assert mutation not in source
    assert 'UPDATE meta_schedule_run' not in source
    assert "ACTIONS=('prepare','schedule-ingest','controls','transfer','renew','enable','inspect','pause','disable')" in source
    enable=source[source.index('def enable('):source.index('\ndef inspect(')]
    assert 'service.transition(' not in enable
    assert 'read_runtime_status(' in enable and 'read_recovery_context(' in enable
    assert 'service_and_options(' not in enable


def test_y_pause_requires_released_runtime_and_preserves_saved_input():
    source=PATH.read_text(encoding='utf-8')
    pause=source[source.index('def pause('):source.index('\ndef disable(')]
    assert "'recoveries':4" in pause and "'released_resources':3" in pause
    assert "intent='disable'" in pause and "'sourceReads':0" in pause
    assert 'UPDATE ' not in pause
