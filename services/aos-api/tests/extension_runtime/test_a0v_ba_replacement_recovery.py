from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_replacement_recovery.py"


def test_ba_replacement_uses_exact_az_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "06849afe-ee19-486d-9d56-5247e947d8ab"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "ee221609-d3d5-4227-8382-063d2ca0eab2"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 128' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 155' in source
    assert 'replacement.DEFINITION_REVISION = 82' in source
    assert 'replacement.INSTALLATION_LABEL = "ba"' in source
    assert "run_definition" not in source
