"""AL is a direct replacement of the formally detached AK generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_al_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_al_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_al_replacement_is_fixed_to_ak_detach_receipt():
    assert recovery.AK_ID == "038bd251-e2e3-415d-8706-955de809b4df"
    assert recovery.AK_GENERATION == "f2c32bd6-699e-4c06-9dee-074e470d20e0"
    assert recovery.AK_DISABLE_OPERATION == "6d44d780-3a8e-4311-8bd5-be028e6e098b"
    assert recovery.ACTIONS == ("preflight", "create-al", "prepare-al", "verify-al",
                                "stage-al", "configure-al", "enable-al", "observe")


def test_al_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("al", action)' in source
    assert 'profile.configure("al", action)' in source
    assert 'action.removesuffix("-al")' in source
    assert "UPDATE extension_runtime_binding" not in source
