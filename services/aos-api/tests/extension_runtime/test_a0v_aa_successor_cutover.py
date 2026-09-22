"""AA cutover has a new operation namespace and group80 predecessor."""
import importlib.util
from pathlib import Path
import sys

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aa_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_aa_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_aa_cutover_is_independent_and_targets_group80():
    assert cutover.OPERATION == "13d3febb-1b70-4ad2-89de-8b47ace6b0f6"
    assert cutover.PREFIX.endswith("aa-cutover-v1")
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 80' in source
    assert 'fallbackAllowed": False' in source
    assert "successor.AA_ID" in source and "successor.AA_GENERATION" in source


def test_aa_cutover_uses_receipt_services_only():
    source = PATH.read_text(encoding="utf-8")
    for method in ("prepare_activation", "begin_activation_commit", "commit_activation",
                   "validate_activation", "resume_activation"):
        assert method in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
