from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_replacement_recovery.py"


def test_bk_replacement_uses_exact_bj_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "2300de61-0b54-413a-97e7-4e37e3b20768"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "2c5d28d5-cfcc-474d-827d-d0031d0de4d8"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 158' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 185' in source
    assert 'replacement.DEFINITION_REVISION = 112' in source
    assert 'replacement.INSTALLATION_LABEL = "bk"' in source
    assert "run_definition" not in source
