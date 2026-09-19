"""AQ cutover uses fixed internal authority and ordered receipts."""
import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aq_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_aq_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_exact():
    assert cutover.OPERATION == "56afe1b2-a69f-4824-ba57-2debab4652e0"
    source = PATH.read_text(encoding="utf-8")
    assert 'request.expectedGroupRevision != 128' in source
    assert '"expectedGroupRevision": 128' in source
    assert 'qyh-clean-generation-aq-activation' in source
    assert '"externalEffectsAllowed": False' in source
    assert '"fallbackAllowed": False' in source
    assert 'choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"]' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
