from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_al_failed_retirement.py"


def test_failed_al_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AL_ID = "071e1c31-c464-4735-952e-17adf0ac97f7"' in source
    assert 'FAILED_ATTEMPT = "3e319ca5-9e8d-4b0e-a034-295cd3e5b645"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert 'row["revision"] != 89' in source
    assert 'row["cutover_group_revision"] != 116' in source
    assert 'dict(definition) != {"revision": 51, "state": "disabled"}' in source
    assert '"failed_attempt": 1, "members": 12, "saved_runs": 12' in source
    assert '"store_receipts": 0, "store_links": 0, "projection_pending": 0' in source
    assert 'operation_kind="disable", installation_id=AL_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source
