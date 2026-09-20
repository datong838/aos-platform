from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bi_terminal_retirement.py"


def test_bi_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"' in source
    assert '"1f8e44c0-c5a7-4099-89a0-6f4998589e4e", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 109" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 153" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 180" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 155" in source
    assert "retirement.DETACHED_GROUP_REVISION = 182" in source
    assert "run_definition" not in source


def test_bi_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
