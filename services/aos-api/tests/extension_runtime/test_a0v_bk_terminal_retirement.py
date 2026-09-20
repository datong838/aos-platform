from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_terminal_retirement.py"


def test_bk_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"' in source
    assert '"c0b032b7-30c1-4260-9b67-99e298347dea", 13, "failed"' in source
    assert '"RECOVERABLE_INGRESS_CANCELLED", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 115" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 159" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 186" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 161" in source
    assert "retirement.DETACHED_GROUP_REVISION = 188" in source
    assert "run_definition" not in source


def test_bk_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
