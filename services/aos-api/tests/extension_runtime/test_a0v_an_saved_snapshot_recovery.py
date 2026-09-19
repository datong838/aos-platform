"""AN transfers the frozen group without source rereads or manual execution."""
import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_an_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_an_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_an_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AN_ID == "7eebbd30-88fe-4c3d-a665-f36c5a9d64bb"
    assert recovery.successor.AN_GENERATION == "41223cb2-28f6-4109-bdaf-e009ca084367"
    assert "current['body']['installationId']!=successor.AM_ID" in source
    assert "current['body']['revision']!=54" in source
    assert "'am-saved-snapshot-recovery-v1'/'renew-result.json'" in source
    assert "'a0v-an-saved-definition-transfer-v1'" in source
    assert "get('revision')!=55" in source
    assert "'a0v-an-saved-input-recovery-v18'" in source
    assert "get('revision')!=18" in source
    assert "get('revision')!=56" in source
    assert "'pause-expired'" in source
    assert recovery.EXPIRED_ATTEMPT == ('1d01cb93-3e8e-4063-b372-bdfb027d2ba3', 11)
    assert "terminal_reason_code='ATTEMPT_LEASE_EXPIRED'" in source
    assert "'abandoned_attempts':1" in source and "'unexpected_attempts':0" in source
    assert "'released_resources':3" in source and "'store_receipt':0" in source
    assert "'current_controls':12" in source
    assert "query.count('%s')!=len(parameters)" in source
    assert "'a0v-an-saved-snapshot-pause-expired-v1'" in source
    assert "get('revision')!=57" in source
    assert "LINK_IDEMPOTENCY_KEY" in source
    assert "'sourceReads':0" in source
    assert "run_definition" not in source
