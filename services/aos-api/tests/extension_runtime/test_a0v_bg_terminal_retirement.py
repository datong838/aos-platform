from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bg_terminal_retirement.py"


def test_bg_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"' in source
    assert '"a42bc506-7e3c-48cd-bde7-1eb0b1adc93f", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 103" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 147" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 174" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 149" in source
    assert "retirement.DETACHED_GROUP_REVISION = 176" in source
    assert "run_definition" not in source


def test_bg_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
