import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aw_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_aw_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_aw_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    base = (PATH.parent / "a0v_av_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert recovery.recovery.INSTALLATION_LABEL == "AW"
    assert recovery.recovery.successor.AW_ID == "f94b9425-9bc4-4369-8ae3-138c50c9ab81"
    assert recovery.recovery.successor.AW_GENERATION == "a92f7bb2-3d90-4d88-9632-5fc9a70bd650"
    assert recovery.recovery.PREDECESSOR_INSTALLATION_ID == "5f01eda8-ca5f-4892-8510-385704ccddb2"
    assert recovery.recovery.PREDECESSOR_DEFINITION_REVISION == 76
    assert recovery.recovery.TRANSFERRED_DEFINITION_REVISION == 77
    assert recovery.recovery.RECOVERY_REVISION == 25
    assert recovery.recovery.ENABLED_DEFINITION_REVISION == 78
    assert recovery.recovery.PAUSED_DEFINITION_REVISION == 79
    assert '"av-saved-snapshot-recovery-v1"' in source
    assert '"a0v-aw-saved-definition-transfer-v1"' in source
    assert '"a0v-aw-saved-input-recovery-v25"' in source
    assert '"sourceReads": 0' in base
    assert "run_definition" not in source and "run_definition" not in base
