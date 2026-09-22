"""AH is a direct replacement of the formally detached AG generation."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ah_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_ah_replacement_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_ah_replacement_is_fixed_to_ag_detach_receipt():
    assert recovery.AG_ID == "37d36900-5b9a-4cd0-9108-4ef5ded25d58"
    assert recovery.AG_GENERATION == "31192641-3558-4cf2-9ad9-ea2375c69900"
    assert recovery.AG_DISABLE_OPERATION == "45789d11-145e-4b4b-84a2-13e6d6fed5b6"
    assert recovery.ACTIONS == ("preflight", "create-ah", "prepare-ah", "verify-ah",
                                "stage-ah", "configure-ah", "enable-ah", "observe")


def test_ah_replacement_uses_normal_lifecycle_and_no_direct_runtime_update():
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert 'profile.lifecycle("ah", action)' in source
    assert 'profile.configure("ah", action)' in source
    assert 'action.removesuffix("-ah")' in source
    assert "UPDATE extension_runtime_binding" not in source
