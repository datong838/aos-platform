from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bh_replacement_recovery.py"


def test_bh_replacement_uses_exact_bg_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "95fbec3c-2248-4d43-928c-17b52d3742da"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "48e4d856-6652-4903-af9f-49bf4774bc0d"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 149' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 176' in source
    assert 'replacement.DEFINITION_REVISION = 103' in source
    assert 'replacement.INSTALLATION_LABEL = "bh"' in source
    assert "run_definition" not in source
