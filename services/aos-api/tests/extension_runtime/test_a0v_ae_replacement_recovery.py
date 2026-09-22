"""AE is a direct replacement of the formally detached AD generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ae_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ae_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ae_replacement_is_fixed_to_ad_detach_receipt():
    assert recovery.AD_ID == "42d9f8bd-11b0-4f8d-8c4d-75458ab23c94"
    assert recovery.AD_GENERATION == "7a2f5483-8ff6-4672-b174-f273885e99d0"
    assert recovery.AD_DISABLE_OPERATION == "1a4ea463-ffef-483c-aaa7-dace2006e119"
    assert recovery.ACTIONS == ("preflight", "create-ae", "prepare-ae", "verify-ae",
                                "stage-ae", "configure-ae", "enable-ae", "observe")


def test_ae_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ae", action)' in source
    assert 'profile.configure("ae", action)' in source
    assert 'action.removesuffix("-ae")' in source
    assert "UPDATE extension_runtime_binding" not in source
