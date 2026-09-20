from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bh_terminal_retirement.py"


def test_bh_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"' in source
    assert '"6d8395b6-b04b-4aa3-b002-9b3618e1eaf3", 61, "failed"' in source
    assert '"RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 106" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 150" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 177" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 152" in source
    assert "retirement.DETACHED_GROUP_REVISION = 179" in source
    assert "run_definition" not in source


def test_bh_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
