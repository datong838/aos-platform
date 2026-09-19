from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_as_successor_business.py"


def test_as_successor_consumes_exact_ar_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AS_ID = "5d0a6d5a-4024-430f-831b-2af15b5ca889"' in source
    assert 'AS_GENERATION = "4cc2dc84-a452-4bac-aa56-0b1519a9826a"' in source
    assert 'AR_ID = "90e9b84e-225c-4c91-a1d4-7d2751d7c7f2"' in source
    assert 'DETACH = "ed0229cc-9771-4f00-a210-4b2a8b7cf76b"' in source
    assert '(old[0]["revision"], old[0]["execution_epoch"]) != (9, 5)' in source
    assert '"expectedGroupRevision": 134' in source
    assert 'row["revision"] != 107' in source
    assert 'row["cutover_group_revision"] != 134' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
