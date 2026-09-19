from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_as_failed_retirement.py"


def test_failed_as_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AS_ID = "5d0a6d5a-4024-430f-831b-2af15b5ca889"' in source
    assert '("af7c1fc1-8283-40d7-ab62-f7d6145417c6", 5, "failed"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert 'row["revision"] != 110' in source
    assert 'row["cutover_group_revision"] != 137' in source
    assert 'dict(definition) != {"revision": 70, "state": "disabled"}' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AS_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
