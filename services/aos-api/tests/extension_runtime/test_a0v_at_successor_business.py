from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_at_successor_business.py"


def test_as_successor_consumes_exact_ar_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AT_ID = "631e6d01-a5bb-4865-95eb-07d5665ed957"' in source
    assert 'AT_GENERATION = "63ea2c87-f185-4b02-b792-1e3073db4a1b"' in source
    assert 'AS_ID = "5d0a6d5a-4024-430f-831b-2af15b5ca889"' in source
    assert 'DETACH = "ae435475-8932-444b-ab41-9660fb966eaf"' in source
    assert '(old[0]["revision"], old[0]["execution_epoch"]) != (8, 4)' in source
    assert '"expectedGroupRevision": 137' in source
    assert 'row["revision"] != 110' in source
    assert 'row["cutover_group_revision"] != 137' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
