"""Y is a direct replacement of the formally detached X generation."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_y_replacement_recovery.py'
SPEC=importlib.util.spec_from_file_location('a0v_y_replacement_recovery',PATH)
recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)


def test_y_replacement_is_fixed_to_x_detach_receipt():
    assert recovery.X_ID=='651dcf7c-08c1-4511-ae23-6e5e864f2b68'
    assert recovery.X_GENERATION=='0663a082-ea85-4110-9730-e13c230cd95c'
    assert recovery.X_DISABLE_OPERATION=='d09d734e-be97-4317-999b-77c96b560be0'
    assert recovery.ACTIONS==('preflight','create-y','prepare-y','verify-y','stage-y','configure-y','enable-y','observe')


def test_y_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source=PATH.read_text(encoding='utf-8')
    assert 'current_installation_ref=predecessor' in source
    assert 'profile.lifecycle("y", action)' in source
    assert 'profile.configure("y", action)' in source
    assert 'UPDATE extension_runtime_binding' not in source
