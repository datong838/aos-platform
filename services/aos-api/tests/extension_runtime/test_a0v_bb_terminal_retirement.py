from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bb_terminal_retirement.py"


def test_terminal_bb_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"' in source
    assert '("ee8dfb28-6b51-47da-9003-2c70d51ea08e", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 88" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 132" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 159" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 134" in source
    assert "retirement.DETACHED_GROUP_REVISION = 161" in source
    assert "a0v-qyh-terminal-bb-retirement-20260920-v1" in source
    assert "a0v_bb_successor_business" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_delivery_and_zero_store_boundary():
    source = (ROOT / "scripts/a0v_aq_failed_retirement.py").read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
