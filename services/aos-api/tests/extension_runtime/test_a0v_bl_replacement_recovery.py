from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_replacement_recovery.py"


def test_bl_replacement_uses_exact_bk_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "6db4b69b-0dbf-4a77-ac71-23cef91c6f50"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "dfce56ec-4bff-4793-a5d5-dab4ad45aa1c"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 161' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 188' in source
    assert 'replacement.DEFINITION_REVISION = 115' in source
    assert 'replacement.INSTALLATION_LABEL = "bl"' in source
    assert "run_definition" not in source
