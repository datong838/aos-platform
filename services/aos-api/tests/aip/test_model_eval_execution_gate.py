"""Approved Model Eval applications are never ordinary Action executions."""

import pytest

from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionTransitionBlocked


@pytest.mark.parametrize("action_id,snapshot_id", [
    ("aip_request_model_eval", "aip_request_model_eval"),
    ("aip_request_model_eval", "other"),
    ("other", "aip_request_model_eval"),
])
def test_model_eval_application_rejects_generic_execution_before_adapter_lookup(
    action_id, snapshot_id,
):
    proposal = {"action_type_id": action_id,
                "action_type_snapshot": {"id": snapshot_id}, "payload": {}}
    with pytest.raises(AipActionTransitionBlocked, match="MODEL_EVAL_APPLICATION_NOT_EXECUTABLE"):
        AipActionExecutionService._reject_bootstrap_action(proposal)
