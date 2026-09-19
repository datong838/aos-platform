"""AN expiry retirement is exact, receipt-bound and never resends Store work."""
import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_an_expired_retirement.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_an_expired_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_an_expired_retirement_authority():
    source = PATH.read_text(encoding="utf-8")
    assert retirement.AN_ID == "7eebbd30-88fe-4c3d-a665-f36c5a9d64bb"
    assert retirement.GENERATION == "41223cb2-28f6-4109-bdaf-e009ca084367"
    assert retirement.ATTEMPT == ("1d01cb93-3e8e-4063-b372-bdfb027d2ba3", 11)
    assert retirement.PREFIX == "a0v-qyh-expired-an-retirement-20260919-v1"
    assert "terminal_reason_code='ATTEMPT_LEASE_EXPIRED'" in source
    assert '"revision": 57, "state": "disabled"' in source
    assert '"revision": 7, "execution_epoch": 4' in source
    assert '"revision": 9, "execution_epoch": 5' in source
    assert 'row["revision"] != 93' in source and 'row["revision"] != 95' in source
    assert 'row["cutover_group_revision"] != 120' in source
    assert 'row["cutover_group_revision"] != 122' in source
    assert "require_released_owner_settlement" in source
    assert '"resendDisable": False' in source
    assert '["fence", "detach"]' in source
    assert '"store_receipts": 0' in source and '"canary": 0' in source
    assert "run_definition" not in source
