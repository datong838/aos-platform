import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aq_failed_retirement.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a0v_aq_failed_retirement_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failed_aq_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AQ_ID = "d6839bf3-55b5-474c-aa21-49966e15db3d"' in source
    assert '("16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82", 11, "failed"' in source
    assert '"revision": 6, "execution_epoch": 3, "enabled": True' in source
    assert '"revision": 8, "execution_epoch": 4, "enabled": False' in source
    assert "DETACHED_ROUTE_REVISION = 104" in source
    assert "DETACHED_GROUP_REVISION = 131" in source
    assert "DEFINITION_REVISION = 66" in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert "run_definition" not in source


def test_completed_disable_preserves_local_claim_intent(tmp_path):
    module = load_module()
    path = tmp_path / "intent.json"
    operation_id = "6db4b69b-0dbf-4a77-ac71-23cef91c6f50"
    intent = {"operationId": operation_id,
              "eventId": "89c74783-9aff-4afd-8368-834db39dff21",
              "resendDisable": False}
    path.write_text(json.dumps(intent), encoding="utf-8")
    assert module.recover_completed_intent(path, operation_id) is False
    assert json.loads(path.read_text(encoding="utf-8")) == intent


def test_completed_disable_rejects_changed_local_claim_intent(tmp_path):
    module = load_module()
    path = tmp_path / "intent.json"
    path.write_text(json.dumps({"operationId": "wrong", "eventId": "wrong",
                                "resendDisable": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="immutable AQ retirement intent differs"):
        module.recover_completed_intent(path, "6db4b69b-0dbf-4a77-ac71-23cef91c6f50")
