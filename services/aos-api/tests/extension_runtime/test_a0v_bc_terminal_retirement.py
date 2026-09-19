from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bc_terminal_retirement.py"


def test_terminal_bc_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "3b895c30-34ca-4710-b978-02645d49c83a"' in source
    assert '("3ab54352-408c-4aae-a150-fb23c64cd7b7", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 91" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 135" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 162" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 137" in source
    assert "retirement.DETACHED_GROUP_REVISION = 164" in source
    assert "a0v-qyh-terminal-bc-retirement-20260920-v1" in source
    assert "a0v_bc_successor_business" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_delivery_and_zero_store_boundary():
    source = (ROOT / "scripts/a0v_aq_failed_retirement.py").read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
