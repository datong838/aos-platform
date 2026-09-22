"""AB is a direct replacement of the formally detached AA generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ab_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ab_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ab_replacement_is_fixed_to_aa_detach_receipt():
    assert recovery.AA_ID == "d0476259-7e04-4cf6-ba94-9d7da1c73db0"
    assert recovery.AA_GENERATION == "44236c8a-cf56-451c-b620-21c63e48d87e"
    assert recovery.AA_DISABLE_OPERATION == "139b08cd-211d-4595-b3bb-90527fe6f2f5"
    assert recovery.ACTIONS == ("preflight", "create-ab", "prepare-ab", "verify-ab",
                                "stage-ab", "configure-ab", "enable-ab", "observe")


def test_ab_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ab", action)' in source
    assert 'profile.configure("ab", action)' in source
    assert "UPDATE extension_runtime_binding" not in source
