from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_av_terminal_retirement.py"


def test_terminal_av_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"' in source
    assert '("42717b1a-1d3b-442d-9b18-683593e4bbbf", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 76" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 117" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 144" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 119" in source
    assert "retirement.DETACHED_GROUP_REVISION = 146" in source
    assert "a0v-qyh-terminal-av-retirement-20260919-v1" in source
    assert "a0v_av_successor_business" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_delivery_and_zero_store_boundary():
    source = (ROOT / "scripts/a0v_aq_failed_retirement.py").read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
