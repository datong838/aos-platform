import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_as_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_as_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_exact_as_cutover_is_registration_bound_and_no_effect():
    assert cutover.OPERATION == "18727254-e4bc-4c6b-b93b-289d8b044dc1"
    source = PATH.read_text(encoding="utf-8")
    assert 'request.expectedGroupRevision != 134' in source
    assert '"expectedGroupRevision": 134' in source
    assert 'qyh-clean-generation-as-activation' in source
    assert 'successor.AS_ID' in source and 'successor.AS_GENERATION' in source
    assert 'successor.AR_ID' not in source and 'successor.AR_GENERATION' not in source
    assert '"externalEffectsAllowed": False' in source
    assert '"fallbackAllowed": False' in source
    assert 'choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"]' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
