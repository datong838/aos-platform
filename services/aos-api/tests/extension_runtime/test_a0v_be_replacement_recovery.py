from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_be_replacement_recovery.py"


def test_be_replacement_uses_exact_bd_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "c2d6ef97-30ec-4980-9421-54a899607853"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "f5f52787-c6f1-468b-9e7e-878113942c65"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "c896fec3-dbe2-46fe-be60-3cc249b4b4ed"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 140' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 167' in source
    assert 'replacement.DEFINITION_REVISION = 94' in source
    assert 'replacement.INSTALLATION_LABEL = "be"' in source
    assert "run_definition" not in source
