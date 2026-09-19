import importlib.util
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ar_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ar_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)

def test_exact_ar_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AR_ID == "90e9b84e-225c-4c91-a1d4-7d2751d7c7f2"
    assert recovery.successor.AR_GENERATION == "b41dc281-a6f7-4357-948b-88519e8b8146"
    assert 'replacement.load("create-ar")' in source
    assert 'current["body"]["installationId"] != successor.AQ_ID' in source
    assert 'current["body"]["revision"] != 66' in source
    assert '"aq-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-ar-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 67' in source
    assert 'idempotency_key="a0v-ar-saved-input-recovery-v22"' in source
    assert 'get("revision") != 22' in source
    assert 'get("revision") != 68' in source
    assert recovery.ACTIONS == ("prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "disable")
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source
    assert "snaqshot" not in source and "aqproved" not in source and "adaqter" not in source
