from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aq_failed_retirement.py"


def test_failed_aq_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AQ_ID = "d6839bf3-55b5-474c-aa21-49966e15db3d"' in source
    assert '("16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82", 11, "failed"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert "DETACHED_ROUTE_REVISION = 104" in source
    assert "DETACHED_GROUP_REVISION = 131" in source
    assert "DEFINITION_REVISION = 66" in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
