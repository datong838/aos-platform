"""Z is a direct replacement of the formally detached Y generation."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_z_replacement_recovery.py'
SPEC=importlib.util.spec_from_file_location('a0v_z_replacement_recovery',PATH)
recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)


def test_z_replacement_is_fixed_to_y_detach_receipt():
    assert recovery.Y_ID=='c76d26b9-8a93-4476-a6fe-206e10930bc9'
    assert recovery.Y_GENERATION=='87cd4104-999d-4224-b1ee-772b22a05445'
    assert recovery.Y_DISABLE_OPERATION=='c08d78ed-6e28-4933-8ed4-9aa7d2f7e6bd'
    assert recovery.ACTIONS==('preflight','create-z','prepare-z','verify-z','stage-z','configure-z','enable-z','observe')


def test_z_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source=PATH.read_text(encoding='utf-8')
    assert 'current_installation_ref=predecessor' in source
    assert 'profile.lifecycle("z", action)' in source
    assert 'profile.configure("z", action)' in source
    assert 'UPDATE extension_runtime_binding' not in source
