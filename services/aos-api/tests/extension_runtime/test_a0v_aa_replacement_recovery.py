"""AA is a direct replacement of the formally detached Z generation."""
import importlib.util
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_aa_replacement_recovery.py'
SPEC=importlib.util.spec_from_file_location('a0v_aa_replacement_recovery',PATH)
recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)


def test_aa_replacement_is_fixed_to_z_detach_receipt():
    assert recovery.Z_ID=='cd426e3a-f5e8-45a2-b6a8-8991294b467e'
    assert recovery.Z_GENERATION=='d49fe4fd-55c8-4688-9602-5dbff946bc36'
    assert recovery.Z_DISABLE_OPERATION=='e907f30d-063e-4ea4-9c1c-8fb339ce7610'
    assert recovery.ACTIONS==('preflight','create-aa','prepare-aa','verify-aa','stage-aa','configure-aa','enable-aa','observe')


def test_aa_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source=PATH.read_text(encoding='utf-8')
    assert 'current_installation_ref=predecessor' in source
    assert 'profile.lifecycle("aa", action)' in source
    assert 'profile.configure("aa", action)' in source
    assert 'UPDATE extension_runtime_binding' not in source
