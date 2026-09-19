from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ar_replacement_recovery.py"


def test_ar_replacement_consumes_exact_aq_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AQ_ID = "d6839bf3-55b5-474c-aa21-49966e15db3d"' in source
    assert 'AQ_GENERATION = "b31be2a7-36fd-4348-9ff8-10939cc3d1cd"' in source
    assert 'AQ_DISABLE_OPERATION = "e45d1c14-ebe0-43e0-bd24-75feb26a9a69"' in source
    assert 'AQ_DETACH_RECEIPT = "5de8ea90-3a52-4556-af26-8c008044cb77"' in source
    assert 'AQ_DETACH_HASH = "sha256:201556d70b44750c0fed8ad71aa09c718b27faf6aa5aeb5d2f36fe4a4ddb098e"' in source
    assert '!= (8, 4)' in source
    assert 'row["revision"] != 104' in source
    assert 'row["cutover_group_revision"] != 131' in source
    assert 'ACTIONS = ("preflight", "create-ar", "prepare-ar", "verify-ar", "stage-ar"' in source
    assert 'action.removesuffix("-ar")' in source
    assert 'action.removesuffix("-aq")' not in source
    assert "snaqshot" not in source
    assert "aqproved" not in source
    assert "adaqter" not in source
    assert "create_approved_first_installation" in source
    assert '"externalEffects": 0' in source
    assert "run_definition" not in source
