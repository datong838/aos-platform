from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_at_failed_retirement.py"


def test_failed_at_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AT_ID = "631e6d01-a5bb-4865-95eb-07d5665ed957"' in source
    assert '("9377beaa-9408-483c-95bb-b432c7aefc70", 11, "failed"' in source
    assert '("b7fd50e2-91a8-40a3-8585-0895404d5a5f", 11, "failed"' in source
    assert '("e512e4d8-25e0-41e0-b624-8b47a3037db2", 11, "failed"' in source
    assert '("0b142866-7a0d-483c-b103-523c1612d425", 5, "failed"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert 'row["revision"] != 113' in source
    assert 'row["cutover_group_revision"] != 140' in source
    assert 'dict(definition) != {"revision": 73, "state": "disabled"}' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AT_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
