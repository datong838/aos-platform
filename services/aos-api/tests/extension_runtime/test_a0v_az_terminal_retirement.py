from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_az_terminal_retirement.py"


def test_terminal_az_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"' in source
    assert '("5505b051-79f8-47a7-b2e2-4ddfc0893eb1", 61, "failed"' in source
    assert '("af15b2e5-7c72-47f0-9e1d-79855a970fd6", 4, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 82" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 126" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 153" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 128" in source
    assert "retirement.DETACHED_GROUP_REVISION = 155" in source
    assert "a0v-qyh-terminal-az-retirement-20260919-v1" in source
    assert "a0v_az_successor_business" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_delivery_and_zero_store_boundary():
    source = (ROOT / "scripts/a0v_aq_failed_retirement.py").read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
