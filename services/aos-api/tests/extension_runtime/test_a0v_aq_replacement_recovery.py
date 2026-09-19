from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aq_replacement_recovery.py"


def test_aq_replacement_consumes_exact_ap_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AP_ID = "733a1366-c61d-4800-9310-4d5d8057ced7"' in source
    assert 'AP_GENERATION = "0640c5ce-f384-457c-94d2-3355faa39f46"' in source
    assert 'AP_DISABLE_OPERATION = "feefe9f4-0dba-442f-a87a-e6b90509c583"' in source
    assert 'AP_DETACH_RECEIPT = "bef5442a-eb6d-43bd-b304-6a11ba8463ae"' in source
    assert 'AP_DETACH_HASH = "sha256:ff3ee5af04d0470b74891dcc8b664afa005358c8ded067ebfe9e6273e0120902"' in source
    assert '!= (8, 4)' in source
    assert 'row["revision"] != 101' in source
    assert 'row["cutover_group_revision"] != 128' in source
    assert 'ACTIONS = ("preflight", "create-aq", "prepare-aq", "verify-aq", "stage-aq"' in source
    assert 'action.removesuffix("-aq")' in source
    assert 'action.removesuffix("-ap")' not in source
    assert '"externalEffects": 0' in source
    assert "run_definition" not in source
