from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_terminal_retirement.py"


def test_bd_terminal_retirement_is_exact_and_fail_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "c2d6ef97-30ec-4980-9421-54a899607853"' in source
    assert '"f1e89789-86ca-4cd5-9854-c75e1c41db94", 61, "failed"' in source
    assert '"RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 94" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 138" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 165" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 140" in source
    assert "retirement.DETACHED_GROUP_REVISION = 167" in source
    assert "run_definition" not in source


def test_bd_terminal_retirement_uses_one_disable_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "retirement.FAILED_ATTEMPTS = ((" in source
    assert "resendDisable" not in source
