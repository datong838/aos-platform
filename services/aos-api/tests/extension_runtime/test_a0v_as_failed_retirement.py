from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_as_failed_retirement.py"


def test_failed_as_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AS_ID = "5d0a6d5a-4024-430f-831b-2af15b5ca889"' in source
    assert '("af7c1fc1-8283-40d7-ab62-f7d6145417c6", 5, "failed"' in source
    assert 'ACTIVE_BINDING_REVISION = 6' in source
    assert 'DETACHED_BINDING_REVISION = 8' in source
    assert 'DETACHED_ROUTE_REVISION = 110' in source
    assert 'DETACHED_GROUP_REVISION = 137' in source
    assert 'DEFINITION_REVISION = 70' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AS_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
