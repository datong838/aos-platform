"""AP transfers the frozen group without source rereads or manual execution."""
import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ap_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ap_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_ap_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AP_ID == "733a1366-c61d-4800-9310-4d5d8057ced7"
    assert recovery.successor.AP_GENERATION == "0640c5ce-f384-457c-94d2-3355faa39f46"
    assert 'current["body"]["installationId"] != successor.AO_ID' in source
    assert 'current["body"]["revision"] != 60' in source
    assert '"ao-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-ap-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 61' in source
    assert 'idempotency_key="a0v-ap-saved-input-recovery-v20"' in source
    assert 'get("revision") != 20' in source
    assert 'get("revision") != 62' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source
