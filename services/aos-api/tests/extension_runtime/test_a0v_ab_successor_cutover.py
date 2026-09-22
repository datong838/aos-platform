"""AB cutover has a new operation namespace and group83 predecessor."""
import importlib.util
from pathlib import Path
import sys

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ab_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ab_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_ab_cutover_is_independent_and_targets_group83():
    assert cutover.OPERATION == "ac34a9a0-f767-447e-b97b-ce3e238ade2c"
    assert cutover.PREFIX.endswith("ab-cutover-v1")
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 83' in source
    assert 'fallbackAllowed": False' in source
    assert "successor.AB_ID" in source and "successor.AB_GENERATION" in source


def test_ab_cutover_uses_receipt_services_only():
    source = PATH.read_text(encoding="utf-8")
    for method in ("prepare_activation", "begin_activation_commit", "commit_activation",
                   "validate_activation", "resume_activation"):
        assert method in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
