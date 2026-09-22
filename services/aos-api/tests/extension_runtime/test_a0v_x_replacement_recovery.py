"""X is a direct replacement of the formally detached W generation."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_x_replacement_recovery.py'
SPEC=importlib.util.spec_from_file_location('a0v_x_replacement_recovery',PATH)
recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)


def test_x_replacement_is_fixed_to_v_detach_receipt():
    assert recovery.W_ID=='79e7c90d-4e3a-43e0-a0ae-b81d75c11e8c'
    assert recovery.W_GENERATION=='b4426dfd-a459-41ad-b1e8-fdc440f788db'
    assert recovery.W_DISABLE_OPERATION=='60b31712-982e-49bb-be8c-8a4294e87d71'
    assert recovery.ACTIONS==('preflight','create-x','prepare-x','verify-x','stage-x','configure-x','enable-x','observe')


def test_x_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source=PATH.read_text(encoding='utf-8')
    assert 'current_installation_ref=predecessor' in source
    assert 'profile.lifecycle("x", action)' in source
    assert 'profile.configure("x", action)' in source
    assert 'UPDATE extension_runtime_binding' not in source
