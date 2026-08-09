"""AIP Task adopts the frozen TaskStatus contract without response reshaping."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from aos_api.aip_task_model import ActionRequest, Task
from aos_api.errors import register_exception_handlers
from aos_api.public_contracts import ContractViolation, TaskStatus
from aos_api.routers import phase3_aip_logic


@pytest.fixture()
def task_client():
    phase3_aip_logic._tasks.clear()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(phase3_aip_logic.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    phase3_aip_logic._tasks.clear()


def test_task_model_maps_created_and_rejects_illegal_transition() -> None:
    task = Task(status="created")
    assert task.status is TaskStatus.PENDING
    task.transition("planning")
    with pytest.raises(ContractViolation):
        task.transition("completed")


@pytest.mark.parametrize("action_type", ["tool_call", "action_writeback", "unknown_plugin_action"])
def test_action_request_refuses_client_risk_downgrade(action_type: str) -> None:
    action = ActionRequest(
        action_type=action_type,
        risk_level="low",
        requires_approval=False,
        side_effect=False,
    )
    assert action.risk_level == "high"
    assert action.requires_approval is True
    assert action.side_effect is True


def test_explicit_side_effect_requires_approval_even_for_read_kind() -> None:
    action = ActionRequest(
        action_type="ontology_query",
        risk_level="low",
        requires_approval=False,
        side_effect=True,
    )
    assert action.risk_level == "medium"
    assert action.requires_approval is True


def test_task_api_keeps_main_shape_and_uses_canonical_lifecycle(task_client) -> None:
    created = task_client.post("/v1/aip/tasks", json={"title": "contract", "steps": []})
    assert created.status_code == 200
    body = created.json()
    assert body["ok"] is True and "task" in body
    task_id = body["task"]["id"]
    assert body["task"]["status"] == "planning"

    approved = task_client.post(
        f"/v1/aip/tasks/{task_id}/plan/approve", json={"approved_by": "reviewer"}
    )
    assert approved.status_code == 200
    assert approved.json()["plan"]["status"] == "approved"
    assert task_client.post(
        f"/v1/aip/tasks/{task_id}/plan/approve", json={"approved_by": "reviewer"}
    ).status_code == 200

    executed = task_client.post(f"/v1/aip/tasks/{task_id}/execute")
    assert executed.status_code == 200
    assert executed.json()["task"]["status"] == "completed"
    conflict = task_client.post(f"/v1/aip/tasks/{task_id}/execute")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "TASK_STATUS_CONFLICT"
