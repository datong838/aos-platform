"""AI is a direct replacement of the formally detached AH generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ai_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ai_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ai_replacement_is_fixed_to_ah_detach_receipt():
    assert recovery.AH_ID == "9fe97ea8-275a-47d0-a0f1-d2064a8d62c6"
    assert recovery.AH_GENERATION == "f2d43d1d-af4e-477d-afd3-4f1174404734"
    assert recovery.AH_DISABLE_OPERATION == "414e0c58-a252-48f6-b834-4fcdd6f5cbba"
    assert recovery.ACTIONS == ("preflight", "create-ai", "prepare-ai", "verify-ai",
                                "stage-ai", "configure-ai", "enable-ai", "observe")


def test_ai_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ai", action)' in source
    assert 'profile.configure("ai", action)' in source
    assert 'action.removesuffix("-ai")' in source
    assert "UPDATE extension_runtime_binding" not in source
