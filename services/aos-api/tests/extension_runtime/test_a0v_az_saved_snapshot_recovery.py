import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_az_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_az_saved_snapshot_recovery", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_exact_az_saved_snapshot_authority():
    base = (PATH.parent / "a0v_av_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert MODULE.recovery.INSTALLATION_LABEL == "AZ"
    assert MODULE.recovery.successor.AZ_ID == "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
    assert MODULE.recovery.successor.AZ_GENERATION == "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"
    assert MODULE.recovery.PREDECESSOR_INSTALLATION_ID == "be884663-0dba-4d9b-aa56-84caaf01147d"
    assert MODULE.recovery.PREDECESSOR_DEFINITION_REVISION == 79
    assert MODULE.recovery.TRANSFERRED_DEFINITION_REVISION == 80
    assert MODULE.recovery.RECOVERY_REVISION == 26
    assert MODULE.recovery.ENABLED_DEFINITION_REVISION == 81
    assert MODULE.recovery.PAUSED_DEFINITION_REVISION == 82
    assert MODULE.recovery.TERMINAL_FREEZE_OUTCOMES == {
        "FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
    assert '"sourceReads": 0' in base
    assert "run_definition" not in PATH.read_text(encoding="utf-8")
