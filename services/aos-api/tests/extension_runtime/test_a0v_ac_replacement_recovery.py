"""AC is a direct replacement of the formally detached AB generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ac_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ac_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ac_replacement_is_fixed_to_ab_detach_receipt():
    assert recovery.AB_ID == "b57e5f93-f075-45f1-a42c-4340255e4f74"
    assert recovery.AB_GENERATION == "00fba2de-a505-49f1-a3e6-696d7415fc79"
    assert recovery.AB_DISABLE_OPERATION == "ece12713-0ac1-443f-9908-47b67b52909f"
    assert recovery.ACTIONS == ("preflight", "create-ac", "prepare-ac", "verify-ac",
                                "stage-ac", "configure-ac", "enable-ac", "observe")


def test_ac_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ac", action)' in source
    assert 'profile.configure("ac", action)' in source
    assert "UPDATE extension_runtime_binding" not in source
