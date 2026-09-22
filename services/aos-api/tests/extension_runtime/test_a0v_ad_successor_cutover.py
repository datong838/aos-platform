"""AD cutover has a new operation namespace and group89 predecessor."""
import importlib.util
from pathlib import Path
import sys

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ad_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ad_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_ad_cutover_is_independent_and_targets_group89():
    assert cutover.OPERATION == "01e46def-0d00-4e56-bbe4-1f5898e0805f"
    assert cutover.PREFIX.endswith("ad-cutover-v1")
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 89' in source
    assert 'fallbackAllowed": False' in source
    assert "successor.AD_ID" in source and "successor.AD_GENERATION" in source


def test_ad_cutover_uses_receipt_services_only():
    source = PATH.read_text(encoding="utf-8")
    for method in ("prepare_activation", "begin_activation_commit", "commit_activation",
                   "validate_activation", "resume_activation"):
        assert method in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
