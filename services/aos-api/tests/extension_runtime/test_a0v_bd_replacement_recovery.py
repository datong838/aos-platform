from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_replacement_recovery.py"


def test_bd_replacement_uses_exact_bc_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "3b895c30-34ca-4710-b978-02645d49c83a"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "b713c722-902f-4486-b3bb-4eca02a621b7"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "39bb3f98-78b6-444b-9d5c-a51991b03f42"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 137' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 164' in source
    assert 'replacement.DEFINITION_REVISION = 91' in source
    assert 'replacement.INSTALLATION_LABEL = "bd"' in source
    assert "run_definition" not in source
