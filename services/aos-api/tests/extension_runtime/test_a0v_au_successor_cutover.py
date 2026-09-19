import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_au_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_au_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_exact_au_cutover_is_registration_bound_and_no_effect():
    assert cutover.OPERATION == "30f30143-f8d0-4ae5-b2bc-6dbbf681f08c"
    source = PATH.read_text(encoding="utf-8")
    assert 'request.expectedGroupRevision != 140' in source
    assert '"expectedGroupRevision": 140' in source
    assert 'qyh-clean-generation-au-activation' in source
    assert 'successor.AU_ID' in source and 'successor.AU_GENERATION' in source
    assert 'successor.AT_ID' not in source and 'successor.AT_GENERATION' not in source
    assert '"externalEffectsAllowed": False' in source
    assert '"fallbackAllowed": False' in source
    assert 'choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"]' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
