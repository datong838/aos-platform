"""AJ is a direct replacement of the formally detached AI generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aj_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_aj_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_aj_replacement_is_fixed_to_ai_detach_receipt():
    assert recovery.AI_ID == "59d91f1c-efd7-4097-8ce0-1d4fa9452c0f"
    assert recovery.AI_GENERATION == "3512c4da-841c-4bd6-a711-343c163b0632"
    assert recovery.AI_DISABLE_OPERATION == "127bd9f1-efbf-435c-b40d-de8dba61b8a9"
    assert recovery.ACTIONS == ("preflight", "create-aj", "prepare-aj", "verify-aj",
                                "stage-aj", "configure-aj", "enable-aj", "observe")


def test_aj_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("aj", action)' in source
    assert 'profile.configure("aj", action)' in source
    assert 'action.removesuffix("-aj")' in source
    assert "UPDATE extension_runtime_binding" not in source
