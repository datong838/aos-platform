from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ap_successor_business.py"


def test_ap_successor_consumes_exact_ao_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AP_ID = "733a1366-c61d-4800-9310-4d5d8057ced7"' in source
    assert 'AP_GENERATION = "0640c5ce-f384-457c-94d2-3355faa39f46"' in source
    assert 'AO_ID = "d4186607-c93f-4fd0-8daa-46e349184ab9"' in source
    assert 'DETACH = "c98d7a33-2653-42a8-86f1-05f26c09217e"' in source
    assert '"expectedGroupRevision": 125' in source
    assert 'row["revision"] != 98' in source
    assert 'row["cutover_group_revision"] != 125' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
