"""AM transfers the frozen group without source rereads or manual execution."""
import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_am_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_am_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_am_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AM_ID == "fd28d180-db24-4568-a848-101fcd3aa3c5"
    assert recovery.successor.AM_GENERATION == "d6bc117e-d19d-4413-beb4-02884206e290"
    assert "current['body']['installationId']!=successor.AL_ID" in source
    assert "current['body']['revision']!=51" in source
    assert "'al-saved-snapshot-recovery-v1'/'renew-result.json'" in source
    assert "'a0v-am-saved-definition-transfer-v1'" in source
    assert "get('revision')!=52" in source
    assert "'a0v-am-saved-input-recovery-v17'" in source
    assert "get('revision')!=17" in source
    assert "get('revision')!=53" in source
    assert "'pause-failed'" in source
    assert "('7d6cc3aa-881d-4aff-ac30-58978d06e85d',627)" in source
    assert "('38e5c7b9-fa37-4d3f-8f3f-769b995b4db3',86)" in source
    assert "'failed_attempts':2" in source and "'unexpected_attempts':0" in source
    assert "'expired_controls':12" in source and "'store_receipt':0" in source
    assert "query.count('%s')!=len(parameters)" in source
    assert "'a0v-am-saved-snapshot-pause-failed-v1'" in source
    assert "'sourceReads':0" in source
    assert "run_definition" not in source
