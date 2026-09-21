from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_cq_blocked_retirement.py"
BASE = ROOT / "scripts/a0v_as_failed_retirement.py"


def test_cq_retirement_fixes_blocked_zero_attempt_boundary():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AS_ID = successor.CQ_ID' in source
    assert "retirement.FAILED_ATTEMPTS = ()" in source
    assert "retirement.ACTIVE_BINDING_REVISION = 9" in source
    assert "retirement.ACTIVE_ROUTE_EXECUTION_EPOCH = 3" in source
    assert "retirement.DETACHED_BINDING_REVISION = 11" in source
    assert "retirement.DEFINITION_REVISION = 193" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 252" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 254" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_owner_delivery_and_saved_runs():
    source = BASE.read_text(encoding="utf-8")
    assert "operation_kind=\"disable\", installation_id=AS_ID" in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
    assert "UPDATE meta_schedule_run" not in source
