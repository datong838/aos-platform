from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_be_terminal_retirement.py"


def test_be_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"' in source
    assert '"041843a3-2cf0-4211-bc16-00e823c210bc", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 97" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 141" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 168" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 143" in source
    assert "retirement.DETACHED_GROUP_REVISION = 170" in source
    assert "run_definition" not in source


def test_be_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = ((" in source
    assert "resendDisable" not in source
