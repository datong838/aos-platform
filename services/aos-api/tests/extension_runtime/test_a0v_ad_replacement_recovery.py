"""AD is a direct replacement of the formally detached AC generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ad_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ad_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ad_replacement_is_fixed_to_ac_detach_receipt():
    assert recovery.AC_ID == "4fbd0873-dede-4c3c-9db8-29c3e14c2c48"
    assert recovery.AC_GENERATION == "cdfa92eb-a695-46e7-9ed4-35a296321403"
    assert recovery.AC_DISABLE_OPERATION == "ae8ad4c2-af80-4d2f-82ed-ec421c8e0975"
    assert recovery.ACTIONS == ("preflight", "create-ad", "prepare-ad", "verify-ad",
                                "stage-ad", "configure-ad", "enable-ad", "observe")


def test_ad_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ad", action)' in source
    assert 'profile.configure("ad", action)' in source
    assert "UPDATE extension_runtime_binding" not in source
