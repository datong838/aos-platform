"""AF is a direct replacement of the formally detached AE generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_af_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_af_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_af_replacement_is_fixed_to_ae_detach_receipt():
    assert recovery.AE_ID == "d02f90f2-eb0e-4859-ad58-35b17ddbcd6a"
    assert recovery.AE_GENERATION == "36a57887-4f28-45e7-8515-2d94a343b5ed"
    assert recovery.AE_DISABLE_OPERATION == "f2ac688e-dac3-433a-859c-3e3424957064"
    assert recovery.ACTIONS == ("preflight", "create-af", "prepare-af", "verify-af",
                                "stage-af", "configure-af", "enable-af", "observe")


def test_af_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("af", action)' in source
    assert 'profile.configure("af", action)' in source
    assert 'action.removesuffix("-af")' in source
    assert "UPDATE extension_runtime_binding" not in source
