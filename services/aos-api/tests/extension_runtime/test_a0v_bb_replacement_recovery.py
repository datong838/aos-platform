from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bb_replacement_recovery.py"


def test_bb_replacement_uses_exact_ba_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "4668c723-0acc-446a-9c0d-80118e2f380c"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "707b4a88-2823-4368-81c6-5e5525c3ea48"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 131' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 158' in source
    assert 'replacement.DEFINITION_REVISION = 85' in source
    assert 'replacement.INSTALLATION_LABEL = "bb"' in source
    assert "run_definition" not in source
