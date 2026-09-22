"""AG is a direct replacement of the formally detached AF generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ag_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ag_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ag_replacement_is_fixed_to_af_detach_receipt():
    assert recovery.AF_ID == "0bf928a9-877a-4b97-9778-7f678d6cd7d4"
    assert recovery.AF_GENERATION == "173e267c-f031-4fda-b801-bc9e0a0d2264"
    assert recovery.AF_DISABLE_OPERATION == "5ae15307-bb70-41ff-925d-8c8a25ec252c"
    assert recovery.ACTIONS == ("preflight", "create-ag", "prepare-ag", "verify-ag",
                                "stage-ag", "configure-ag", "enable-ag", "observe")


def test_ag_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ag", action)' in source
    assert 'profile.configure("ag", action)' in source
    assert 'action.removesuffix("-ag")' in source
    assert "UPDATE extension_runtime_binding" not in source
