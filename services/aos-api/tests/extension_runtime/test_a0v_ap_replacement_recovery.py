from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ap_replacement_recovery.py"


def test_ap_replacement_consumes_exact_ao_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AO_ID = "d4186607-c93f-4fd0-8daa-46e349184ab9"' in source
    assert 'AO_GENERATION = "00bb99df-d436-483d-86df-496718c6f129"' in source
    assert 'AO_DISABLE_OPERATION = "44d42ccb-07a2-437a-8405-ea703f812803"' in source
    assert 'AO_DETACH_RECEIPT = "c98d7a33-2653-42a8-86f1-05f26c09217e"' in source
    assert 'AO_DETACH_HASH = "sha256:b4e2969a445b0459dd0e43376d600ab87a515374774e3434d31a28eb014c29f9"' in source
    assert '!= (8, 4)' in source
    assert 'row["revision"] != 98' in source
    assert 'row["cutover_group_revision"] != 125' in source
    assert 'ACTIONS = ("preflight", "create-ap", "prepare-ap", "verify-ap", "stage-ap"' in source
    assert '"externalEffects": 0' in source
    assert "run_definition" not in source
