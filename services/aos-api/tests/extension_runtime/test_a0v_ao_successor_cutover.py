"""AO cutover uses fixed internal authority and ordered receipts."""
import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ao_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ao_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_exact():
    assert cutover.OPERATION == "cfad91b4-3c41-4104-b8e9-1d7da2e9e689"
    source = PATH.read_text(encoding="utf-8")
    assert 'request.expectedGroupRevision != 122' in source
    assert '"expectedGroupRevision": 122' in source
    assert 'qyh-clean-generation-ao-activation' in source
    assert '"externalEffectsAllowed": False' in source
    assert '"fallbackAllowed": False' in source
    assert 'choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"]' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
