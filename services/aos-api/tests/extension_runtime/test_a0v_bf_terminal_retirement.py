from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_terminal_retirement.py"


def test_bf_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"' in source
    assert '"0a79f73d-7243-4778-90af-2e2109115e73", 61, "failed"' in source
    assert '"RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"' in source
    assert '"b61340d4-391f-415d-ac77-65ed8f72321d", 10, "failed"' in source
    assert '"RECOVERABLE_INGRESS_CANCELLED", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 100" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 144" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 171" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 146" in source
    assert "retirement.DETACHED_GROUP_REVISION = 173" in source
    assert "run_definition" not in source


def test_bf_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = (" in source
    assert "resendDisable" not in source
