"""AT replacement accepts only AS's exact formal detach boundary."""
import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_at_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_at_replacement_recovery", PATH)
replacement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replacement)


def test_exact_as_predecessor_and_detach_receipt_are_fixed():
    assert replacement.AS_ID == "5d0a6d5a-4024-430f-831b-2af15b5ca889"
    assert replacement.AS_GENERATION == "4cc2dc84-a452-4bac-aa56-0b1519a9826a"
    assert replacement.AS_DISABLE_OPERATION == "410d2bcd-3c56-4ea5-af0f-e599a08bc1ba"
    assert replacement.AS_DETACH_RECEIPT == "ae435475-8932-444b-ab41-9660fb966eaf"
    source = PATH.read_text(encoding="utf-8")
    assert '(8, 4)' in source
    assert 'row["revision"] != 110' in source
    assert 'row["cutover_group_revision"] != 137' in source


def test_at_replacement_remains_lifecycle_only():
    source = PATH.read_text(encoding="utf-8")
    assert '"prepare-at", "verify-at", "stage-at"' in source
    assert '"configure-at", "enable-at", "observe"' in source
    assert "run_definition" not in source
    assert "ecom_link" not in source
