import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ax_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ax_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_ax_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    base = (PATH.parent / "a0v_av_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert recovery.recovery.INSTALLATION_LABEL == "AX"
    assert recovery.recovery.successor.AX_ID == "be884663-0dba-4d9b-aa56-84caaf01147d"
    assert recovery.recovery.successor.AX_GENERATION == "a14c911b-6796-4d22-a3b0-1817cf502de9"
    assert recovery.recovery.PREDECESSOR_INSTALLATION_ID == "5f01eda8-ca5f-4892-8510-385704ccddb2"
    assert recovery.recovery.PREDECESSOR_DEFINITION_REVISION == 76
    assert recovery.recovery.TRANSFERRED_DEFINITION_REVISION == 77
    assert recovery.recovery.RECOVERY_REVISION == 25
    assert recovery.recovery.ENABLED_DEFINITION_REVISION == 78
    assert recovery.recovery.PAUSED_DEFINITION_REVISION == 79
    assert recovery.recovery.attempt_guard_module() is recovery.ax_guard
    assert recovery.recovery.TERMINAL_FREEZE_OUTCOMES == {
        "FAILED_FREEZE_BOUNDARY", "ABANDONED_FREEZE_BOUNDARY"}
    assert '"av-saved-snapshot-recovery-v1"' in source
    assert '"a0v-ax-saved-definition-transfer-v1"' in source
    assert '"a0v-ax-saved-input-recovery-v25"' in source
    assert '"sourceReads": 0' in base
    assert "run_definition" not in source and "run_definition" not in base
