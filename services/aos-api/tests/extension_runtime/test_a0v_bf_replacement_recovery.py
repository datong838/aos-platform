from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_replacement_recovery.py"


def test_bf_replacement_uses_exact_be_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "dbe83c13-de44-4f49-8834-c6ac0a662782"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "2b758ca2-8afd-48a4-af23-6367fe505758"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 143' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 170' in source
    assert 'replacement.DEFINITION_REVISION = 97' in source
    assert 'replacement.INSTALLATION_LABEL = "bf"' in source
    assert "run_definition" not in source
