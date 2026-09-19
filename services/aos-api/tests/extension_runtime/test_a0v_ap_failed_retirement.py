from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ap_failed_retirement.py"


def test_failed_ap_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AP_ID = "733a1366-c61d-4800-9310-4d5d8057ced7"' in source
    assert '("93e2fc05-ebcb-46e1-8288-2bb0be32ae31", 11, "failed"' in source
    assert '("434092c8-c519-440f-8822-5ecff74287b5", 2, "abandoned"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert 'row["revision"] != 101' in source
    assert 'row["cutover_group_revision"] != 128' in source
    assert 'dict(definition) != {"revision": 63, "state": "disabled"}' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AP_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
