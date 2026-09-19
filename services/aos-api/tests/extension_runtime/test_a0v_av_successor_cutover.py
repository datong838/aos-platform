import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_av_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_av_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_exact_av_cutover_is_registration_bound_and_no_effect():
    assert cutover.OPERATION == "9346c5d1-184d-44e0-a0ed-77b71c2d36c6"
    assert cutover.PREDECESSOR_GROUP_REVISION == 143
    source = PATH.read_text(encoding="utf-8")
    assert 'request.expectedGroupRevision != PREDECESSOR_GROUP_REVISION' in source
    assert '"expectedGroupRevision": PREDECESSOR_GROUP_REVISION' in source
    assert 'qyh-clean-generation-av-activation' in source
    assert 'successor.AV_ID' in source and 'successor.AV_GENERATION' in source
    assert 'successor.AU_ID' not in source and 'successor.AU_GENERATION' not in source
    assert '"externalEffectsAllowed": False' in source
    assert '"fallbackAllowed": False' in source
    assert 'choices=["approve", "prepare", "pause", "commit", "validate", "resume", "inspect"]' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
