from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bg_replacement_recovery.py"


def test_bg_replacement_uses_exact_bf_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "da0a2b14-f0f7-4f21-8513-c56bf4fbeb29"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "03852ebe-20e0-4a41-a5fc-c9eb3aa927dd"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 146' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 173' in source
    assert 'replacement.DEFINITION_REVISION = 100' in source
    assert 'replacement.INSTALLATION_LABEL = "bg"' in source
    assert "run_definition" not in source
