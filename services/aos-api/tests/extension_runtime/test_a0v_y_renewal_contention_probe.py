"""Y contention proof is bounded, read-only, and requires a real blocked Host."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_y_renewal_contention_probe.py'
SPEC=importlib.util.spec_from_file_location('a0v_y_renewal_contention_probe',PATH)
probe=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(probe)


def test_probe_is_fixed_to_current_y_and_bounded():
    assert probe.Y_ID=='c76d26b9-8a93-4476-a6fe-206e10930bc9'
    assert probe.GENERATION=='87cd4104-999d-4224-b1ee-772b22a05445'
    assert probe.APPLY_OPERATION=='017a11cc-87d5-468d-b15a-dcf5390a72f4'
    assert probe.STALE_HOLD_SECONDS>3
    assert probe.MAX_LOCK_SECONDS<=30


def test_probe_never_mutates_rows_and_requires_real_lock_wait():
    source=PATH.read_text(encoding='utf-8')
    assert 'FOR UPDATE' in source and "wait_event_type='Lock'" in source
    assert 'pg_stat_clear_snapshot()' in source
    assert 'health <= released' in source
    assert 'UPDATE ' not in source and 'INSERT ' not in source and 'DELETE ' not in source
