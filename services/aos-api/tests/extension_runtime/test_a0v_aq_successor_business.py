from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aq_successor_business.py"


def test_aq_successor_consumes_exact_ap_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AQ_ID = "d6839bf3-55b5-474c-aa21-49966e15db3d"' in source
    assert 'AQ_GENERATION = "b31be2a7-36fd-4348-9ff8-10939cc3d1cd"' in source
    assert 'AP_ID = "733a1366-c61d-4800-9310-4d5d8057ced7"' in source
    assert 'DETACH = "bef5442a-eb6d-43bd-b304-6a11ba8463ae"' in source
    assert '"expectedGroupRevision": 128' in source
    assert 'row["revision"] != 101' in source
    assert 'row["cutover_group_revision"] != 128' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
