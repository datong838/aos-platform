from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_terminal_retirement.py"


def test_bl_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"' in source
    assert '"06352972-8c80-4291-aece-2474209e6a76", 46, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 118" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 162" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 189" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 164" in source
    assert "retirement.DETACHED_GROUP_REVISION = 191" in source
    assert "run_definition" not in source


def test_bl_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
