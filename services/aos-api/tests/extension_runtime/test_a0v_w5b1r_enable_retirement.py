from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
import a0v_w5b1r_enable_retirement as retirement


def test_request_refuses_existing_state_before_reading_database(monkeypatch, tmp_path):
    monkeypatch.setattr(retirement, "STATE", tmp_path)
    monkeypatch.setattr(retirement, "preflight", lambda: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="EXISTING_STATE_RECONCILE_FIRST"):
        retirement.request_disable()


def test_process_requires_private_accepted_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(retirement, "STATE", tmp_path)
    with pytest.raises(ValueError, match="PRIVATE_RESULT_REQUIRED"):
        retirement.process_disable()


def test_process_existing_intent_never_reclaims(monkeypatch, tmp_path):
    monkeypatch.setattr(retirement, "STATE", tmp_path)
    retirement._write("request-result", {"receipt": {"operationId": "00000000-0000-0000-0000-000000000001"}})
    retirement._write("process-intent", {"operationId": "00000000-0000-0000-0000-000000000001"})
    monkeypatch.setattr(retirement.base, "_current", lambda: pytest.fail("must stop before claim"))
    with pytest.raises(ValueError, match="PROCESS_BOUNDARY_UNKNOWN_RECONCILE_FIRST"):
        retirement.process_disable()
