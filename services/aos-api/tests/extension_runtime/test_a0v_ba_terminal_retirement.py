from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_terminal_retirement.py"


def test_terminal_ba_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"' in source
    assert '("a000b48d-52d5-44ce-a3c5-159b40b1f9b6", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 85" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 129" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 156" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 131" in source
    assert "retirement.DETACHED_GROUP_REVISION = 158" in source
    assert "a0v-qyh-terminal-ba-retirement-20260919-v1" in source
    assert "a0v_ba_successor_business" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_delivery_and_zero_store_boundary():
    source = (ROOT / "scripts/a0v_aq_failed_retirement.py").read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
