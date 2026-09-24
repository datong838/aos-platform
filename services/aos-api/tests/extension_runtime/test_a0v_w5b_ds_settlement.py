from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
import a0v_w5b_ds_settlement as settlement


def test_request_refuses_existing_private_boundary_before_database(monkeypatch, tmp_path):
    monkeypatch.setattr(settlement, "STATE", tmp_path)
    monkeypatch.setattr(settlement, "snapshot", lambda: pytest.fail("no database access"))
    with pytest.raises(ValueError, match="EXISTING_STATE_RECONCILE_FIRST"):
        settlement.request_disable()


def test_process_requires_exact_prior_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(settlement, "STATE", tmp_path)
    with pytest.raises(ValueError, match="PRIVATE_RESULT_REQUIRED"):
        settlement.process_disable()


def test_released_precondition_rejects_new_business_attempt(monkeypatch):
    import a0v_ecommerce_current_reinstall as current
    monkeypatch.setattr(current, "require_released_owner_settlement", lambda _:
                        {"etag": 5, "generation": settlement.GENERATION, "bindingRevision": 7})
    value = {"installation": {"head": {"lock_hash": settlement.LOCK},
                              "bindings": [{"execution_epoch": 4}]},
             "schedules": {"total": 12, "enabled": 0}, "activeAttempts": 1,
             "canaryBindings": 0, "oldDefinition": {"state": "disabled"},
             "newDefinition": None}
    with pytest.raises(ValueError, match="RELEASED_PRECONDITION_DRIFT"):
        settlement.require_released(value)


def test_reconcile_records_verified_concurrent_delivery_without_claim(monkeypatch, tmp_path):
    monkeypatch.setattr(settlement, "STATE", tmp_path)
    monkeypatch.setattr(settlement, "audit", lambda: {
        "operationId": "op", "operationStatus": "succeeded", "deliveredEvents": 2})
    result = settlement.reconcile()
    assert result["processedByThisExecutor"] is False
    assert result["resendDisable"] is False
    assert (tmp_path / "process-result.json").is_file()
