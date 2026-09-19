from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ar_successor_business.py"

def test_ar_successor_consumes_exact_aq_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AR_ID = "90e9b84e-225c-4c91-a1d4-7d2751d7c7f2"' in source
    assert 'AR_GENERATION = "b41dc281-a6f7-4357-948b-88519e8b8146"' in source
    assert 'AQ_ID = "d6839bf3-55b5-474c-aa21-49966e15db3d"' in source
    assert 'DETACH = "5de8ea90-3a52-4556-af26-8c008044cb77"' in source
    assert '"expectedGroupRevision": 131' in source
    assert 'row["revision"] != 104' in source
    assert 'row["cutover_group_revision"] != 131' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
    assert "snaqshot" not in source and "aqproved" not in source and "adaqter" not in source
