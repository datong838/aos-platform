import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ba_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ba_saved_snapshot_recovery", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_exact_ba_saved_snapshot_authority():
    assert MODULE.recovery.INSTALLATION_LABEL == "BA"
    assert MODULE.recovery.successor.BA_ID == "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
    assert MODULE.recovery.PREDECESSOR_DEFINITION_REVISION == 82
    assert MODULE.recovery.TRANSFERRED_DEFINITION_REVISION == 83
    assert MODULE.recovery.RECOVERY_REVISION == 27
    assert MODULE.recovery.ENABLED_DEFINITION_REVISION == 84
    assert MODULE.recovery.PAUSED_DEFINITION_REVISION == 85
    assert MODULE.recovery.EXPECTED_TERMINAL_ATTEMPT_COUNT == 1
    assert "run_definition" not in PATH.read_text(encoding="utf-8")
