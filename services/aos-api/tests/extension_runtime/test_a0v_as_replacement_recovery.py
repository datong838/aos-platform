"""AS replacement accepts only AR's exact formal detach boundary."""
import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_as_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_as_replacement_recovery", PATH)
replacement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replacement)


def test_exact_ar_predecessor_and_detach_receipt_are_fixed():
    assert replacement.AR_ID == "90e9b84e-225c-4c91-a1d4-7d2751d7c7f2"
    assert replacement.AR_GENERATION == "b41dc281-a6f7-4357-948b-88519e8b8146"
    assert replacement.AR_DISABLE_OPERATION == "ffe632e9-3591-4dc9-b244-cdb12e5fcf00"
    assert replacement.AR_DETACH_RECEIPT == "ed0229cc-9771-4f00-a210-4b2a8b7cf76b"
    source = PATH.read_text(encoding="utf-8")
    assert '(9, 5)' in source
    assert 'row["revision"] != 107' in source
    assert 'row["cutover_group_revision"] != 134' in source


def test_as_replacement_remains_lifecycle_only():
    source = PATH.read_text(encoding="utf-8")
    assert '"prepare-as", "verify-as", "stage-as"' in source
    assert '"configure-as", "enable-as", "observe"' in source
    assert "run_definition" not in source
    assert "ecom_link" not in source
