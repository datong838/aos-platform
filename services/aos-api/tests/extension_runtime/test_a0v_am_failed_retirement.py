from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_am_failed_retirement.py"


def test_failed_am_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AM_ID = "fd28d180-db24-4568-a848-101fcd3aa3c5"' in source
    assert '("7d6cc3aa-881d-4aff-ac30-58978d06e85d", 627)' in source
    assert '("38e5c7b9-fa37-4d3f-8f3f-769b995b4db3", 86)' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert 'row["revision"] != 92' in source
    assert 'row["cutover_group_revision"] != 119' in source
    assert 'dict(definition) != {"revision": 54, "state": "disabled"}' in source
    assert '"failed_attempts": 2, "unexpected_attempts": 0' in source
    assert '"store_receipts": 0, "store_links": 0, "projection_pending": 0' in source
    assert 'operation_kind="disable", installation_id=AM_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
