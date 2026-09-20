from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bj_replacement_recovery.py"


def test_bj_replacement_uses_exact_bi_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "96f687af-97ea-44cc-97e6-0c1cd292a8cf"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "64375b18-389a-4e5b-bd17-c7e03a63edd6"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 155' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 182' in source
    assert 'replacement.DEFINITION_REVISION = 109' in source
    assert 'replacement.INSTALLATION_LABEL = "bj"' in source
    assert "run_definition" not in source
