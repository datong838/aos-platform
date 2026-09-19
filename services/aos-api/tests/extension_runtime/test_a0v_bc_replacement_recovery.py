from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bc_replacement_recovery.py"


def test_bc_replacement_uses_exact_bb_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "5e1e9518-eaf1-4fc0-9d6c-30721e342c6a"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "0dd16596-c66b-4390-b9dc-0504c1a822c7"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 134' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 161' in source
    assert 'replacement.DEFINITION_REVISION = 88' in source
    assert 'replacement.INSTALLATION_LABEL = "bc"' in source
    assert "run_definition" not in source
