from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ao_replacement_recovery.py"


def test_ao_replacement_is_bound_to_an_detach_and_ordered_lifecycle():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AN_ID = "7eebbd30-88fe-4c3d-a665-f36c5a9d64bb"' in source
    assert 'AN_GENERATION = "41223cb2-28f6-4109-bdaf-e009ca084367"' in source
    assert 'AN_DISABLE_OPERATION = "7fdd2161-1732-4a14-8aa4-101be445e801"' in source
    assert 'AN_DETACH_RECEIPT = "79254572-7c39-469e-860b-1ae2f36b4b6e"' in source
    assert 'AN_DETACH_HASH = "sha256:f28bc0f92775768a3aa7c6354cb03f5f7b77f61353888e3116f60014232678f4"' in source
    assert '(bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)' in source
    assert 'row["revision"] != 95' in source
    assert 'row["cutover_group_revision"] != 122' in source
    assert 'current_installation_ref=predecessor' in source
    assert '"preflight", "create-ao", "prepare-ao", "verify-ao", "stage-ao"' in source
    assert '"configure-ao", "enable-ao", "observe"' in source
    assert 'action.removesuffix("-ao")' in source
    assert "run_definition" not in source
