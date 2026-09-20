from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bj_terminal_retirement.py"


def test_bj_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"' in source
    assert '"6746bf55-daf2-4bc6-a8fe-038f3ff0bcba", 61, "abandoned"' in source
    assert '"ATTEMPT_LEASE_EXPIRED", None' in source
    assert "retirement.DEFINITION_REVISION = 112" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 156" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 183" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 158" in source
    assert "retirement.DETACHED_GROUP_REVISION = 185" in source
    assert "run_definition" not in source


def test_bj_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
