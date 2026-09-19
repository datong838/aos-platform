"""AO transfers the frozen group without source rereads or manual execution."""
import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ao_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ao_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_ao_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AO_ID == "d4186607-c93f-4fd0-8daa-46e349184ab9"
    assert recovery.successor.AO_GENERATION == "00bb99df-d436-483d-86df-496718c6f129"
    assert 'current["body"]["installationId"] != successor.AN_ID' in source
    assert 'current["body"]["revision"] != 57' in source
    assert '"an-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-ao-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 58' in source
    assert 'idempotency_key="a0v-ao-saved-input-recovery-v19"' in source
    assert 'get("revision") != 19' in source
    assert 'get("revision") != 59' in source
    assert recovery.ACTIONS == (
        "prepare", "schedule-ingest", "controls", "transfer", "renew", "enable", "inspect", "disable"
    )
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source
