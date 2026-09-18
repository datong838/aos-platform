"""AK is a direct replacement of the formally detached AJ generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ak_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ak_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ak_replacement_is_fixed_to_ai_detach_receipt():
    assert recovery.AJ_ID == "cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244"
    assert recovery.AJ_GENERATION == "6dc4f34a-5cc6-4b20-bfb8-8a002a7dcd76"
    assert recovery.AJ_DISABLE_OPERATION == "b8a18338-f792-4c21-949e-70a0db4853a3"
    assert recovery.ACTIONS == ("preflight", "create-ak", "prepare-ak", "verify-ak",
                                "stage-ak", "configure-ak", "enable-ak", "observe")


def test_ak_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ak", action)' in source
    assert 'profile.configure("ak", action)' in source
    assert 'action.removesuffix("-ak")' in source
    assert "UPDATE extension_runtime_binding" not in source
