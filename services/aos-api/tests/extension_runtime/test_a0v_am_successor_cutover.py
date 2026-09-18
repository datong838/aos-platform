"""AM cutover uses fixed internal authority and ordered receipts."""
import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_am_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_am_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_exact():
    assert cutover.OPERATION == "23bc8ec0-1a67-4ae8-9210-de67114f7a6a"
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 116' in source
    assert 'qyh-clean-generation-am-activation' in source
    assert '"externalEffectsAllowed": False' in source
    assert '"fallbackAllowed": False' in source
    assert 'choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"]' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
