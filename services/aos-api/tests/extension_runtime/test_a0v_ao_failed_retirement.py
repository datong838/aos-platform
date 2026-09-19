from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ao_failed_retirement.py"


def test_failed_ao_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AO_ID = "d4186607-c93f-4fd0-8daa-46e349184ab9"' in source
    assert '("67c2331d-b73f-4863-b881-0d67e6c55508", 255, "abandoned"' in source
    assert '("dbcde37a-95ef-4f95-a586-61ab283cf5bb", 11, "failed"' in source
    assert '("70241ae9-7b18-40f5-9309-563594cd3e37", 2, "abandoned"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert 'row["revision"] != 98' in source
    assert 'row["cutover_group_revision"] != 125' in source
    assert 'dict(definition) != {"revision": 60, "state": "disabled"}' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AO_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
