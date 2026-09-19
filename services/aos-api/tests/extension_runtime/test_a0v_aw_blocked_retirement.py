from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aw_blocked_retirement.py"
BASE = ROOT / "scripts/a0v_as_failed_retirement.py"


def test_aw_retirement_fixes_blocked_zero_attempt_boundary():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AS_ID = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"' in source
    assert 'retirement.FAILED_ATTEMPTS = ()' in source
    assert 'retirement.ACTIVE_BINDING_REVISION = 9' in source
    assert 'retirement.ACTIVE_ROUTE_EXECUTION_EPOCH = 3' in source
    assert 'retirement.DETACHED_BINDING_REVISION = 11' in source
    assert 'retirement.DEFINITION_REVISION = 76' in source
    assert 'retirement.ACTIVE_ROUTE_REVISION = 120' in source
    assert 'retirement.DETACHED_ROUTE_REVISION = 122' in source


def test_shared_retirement_keeps_single_owner_delivery_and_saved_runs():
    source = BASE.read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AS_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
    assert "UPDATE meta_schedule_run" not in source
