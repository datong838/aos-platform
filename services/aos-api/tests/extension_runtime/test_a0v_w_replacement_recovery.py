"""W is a direct replacement of the formally detached V generation."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_w_replacement_recovery.py'
SPEC=importlib.util.spec_from_file_location('a0v_w_replacement_recovery',PATH)
recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)


def test_w_replacement_is_fixed_to_v_detach_receipt():
    assert recovery.V_ID=='33a63ef9-405d-4893-b9f8-dd569f64b46b'
    assert recovery.V_GENERATION=='5a9ce3d0-c4c4-4545-a5c7-d286fdb62ddb'
    assert recovery.V_DISABLE_OPERATION=='f822ddde-d122-47e5-ae43-ef2565594cb7'
    assert recovery.ACTIONS==('preflight','create-w','prepare-w','verify-w','stage-w','configure-w','enable-w','observe')


def test_w_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source=PATH.read_text(encoding='utf-8')
    assert 'current_installation_ref=predecessor' in source
    assert 'profile.lifecycle("w", action)' in source
    assert 'profile.configure("w", action)' in source
    assert 'UPDATE extension_runtime_binding' not in source
