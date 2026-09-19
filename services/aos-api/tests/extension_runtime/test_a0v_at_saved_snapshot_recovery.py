import importlib.util
import sys
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_at_saved_snapshot_recovery.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_at_saved_snapshot_recovery", PATH)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_exact_at_saved_snapshot_authority():
    source = PATH.read_text(encoding="utf-8")
    assert recovery.GROUP == "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
    assert recovery.successor.AT_ID == "631e6d01-a5bb-4865-95eb-07d5665ed957"
    assert recovery.successor.AT_GENERATION == "63ea2c87-f185-4b02-b792-1e3073db4a1b"
    assert 'replacement.load("create-at")' in source
    assert 'current["body"]["installationId"] != successor.AS_ID' in source
    assert 'current["body"]["revision"] != 70' in source
    assert '"as-saved-snapshot-recovery-v1" / "renew-result.json"' in source
    assert 'idempotency_key="a0v-at-saved-definition-transfer-v1"' in source
    assert 'get("revision") != 71' in source
    assert 'idempotency_key="a0v-at-saved-input-recovery-v23"' in source
    assert 'get("revision") != 23' in source
    assert 'get("revision") != 72' in source
    assert recovery.ACTIONS == (
        "prepare", "schedule-ingest", "controls", "transfer", "renew", "enable",
        "inspect", "pause-failed", "disable",
    )
    assert '"sourceReads": 0' in source
    assert "def pause_failed" in source and "ATTEMPT_ID" not in source
    assert "run_definition" not in source
    assert 'intent="disable"' in source
    assert '"attemptCount": 4' in source
    assert 'get("revision") != 73' in source
