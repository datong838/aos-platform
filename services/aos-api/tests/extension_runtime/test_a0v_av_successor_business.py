from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_av_successor_business.py"


def test_av_successor_consumes_exact_au_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AV_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"' in source
    assert 'AV_GENERATION = "17104053-f4c9-47e1-89b0-f3f353076dda"' in source
    assert 'AU_ID = "eddc89f9-1e91-4e42-be4e-7d81dc941c1d"' in source
    assert 'DETACH = "7e223943-906f-4efe-8d4b-da7fc2424e48"' in source
    assert '(old[0]["revision"], old[0]["execution_epoch"]) != (9, 5)' in source
    assert '"expectedGroupRevision": 143' in source
    assert 'row["revision"] != 116' in source
    assert 'row["cutover_group_revision"] != 143' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
