from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bi_replacement_recovery.py"


def test_bi_replacement_uses_exact_bh_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "33167268-e7e6-42fc-90f9-e2cb83e6f932"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "8609e798-2f61-43df-9838-cad7da02c230"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 152' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 179' in source
    assert 'replacement.DEFINITION_REVISION = 106' in source
    assert 'replacement.INSTALLATION_LABEL = "bi"' in source
    assert "run_definition" not in source
