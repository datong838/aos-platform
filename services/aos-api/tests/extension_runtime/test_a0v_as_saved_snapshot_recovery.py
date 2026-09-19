import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_as_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_as_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_as_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AS_ID == "5d0a6d5a-4024-430f-831b-2af15b5ca889"
    assert recovery.successor.AS_GENERATION == "4cc2dc84-a452-4bac-aa56-0b1519a9826a"
    assert 'replacement.load("create-as")' in source
    assert 'current["body"]["installationId"] != successor.AR_ID' in source
    assert 'current["body"]["revision"] != 67' in source
    assert '"aq-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-as-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 68' in source
    assert 'idempotency_key="a0v-as-saved-input-recovery-v22"' in source
    assert 'get("revision") != 22' in source
    assert 'get("revision") != 69' in source
    assert recovery.ACTIONS == ("prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "disable")
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source
