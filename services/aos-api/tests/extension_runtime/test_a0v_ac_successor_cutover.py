"""AC cutover has a new operation namespace and group86 predecessor."""
import importlib.util
from pathlib import Path
import sys

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ac_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ac_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_ac_cutover_is_independent_and_targets_group86():
    assert cutover.OPERATION == "69e0d35c-5aca-462c-afa7-1ba538e4e20e"
    assert cutover.PREFIX.endswith("ac-cutover-v1")
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 86' in source
    assert 'fallbackAllowed": False' in source
    assert "successor.AC_ID" in source and "successor.AC_GENERATION" in source


def test_ac_cutover_uses_receipt_services_only():
    source = PATH.read_text(encoding="utf-8")
    for method in ("prepare_activation", "begin_activation_commit", "commit_activation",
                   "validate_activation", "resume_activation"):
        assert method in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
