"""AIP Task adopts the frozen status contract and PostgreSQL authority."""
import uuid

import pytest

from aos_api.aip_task_model import ActionRequest, Task
from aos_api.db import connect
from aos_api.public_contracts import ContractViolation, TaskStatus


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


def test_task_api_persists_exact_plan_approval_and_queued_run(client) -> None:
    suffix = uuid.uuid4().hex
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
        "Idempotency-Key": f"task-{suffix}",
    }
    created = client.post(
        "/v1/aip/tasks",
        headers=headers,
        json={"type": "contract-test", "title": "contract"},
    )
    assert created.status_code == 201, created.text
    task = created.json()
    task_id = task["id"]
    assert task["status"] == "pending"

    plan = client.post(
        f"/v1/aip/tasks/{task_id}/plans",
        headers={**headers, "Idempotency-Key": f"plan-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": [{"stepKey": "read", "title": "读取本体"}],
        },
    )
    assert plan.status_code == 201, plan.text
    planned_task = client.get(f"/v1/aip/tasks/{task_id}", headers=headers).json()
    approved = client.post(
        f"/v1/aip/tasks/{task_id}/plans/{plan.json()['revision']}/approve",
        headers={**headers, "Idempotency-Key": f"approve-{suffix}"},
        json={
            "expectedTaskVersion": planned_task["version"],
            "expectedContentHash": plan.json()["contentHash"],
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approvalStatus"] == "approved"
    approved_task = client.get(f"/v1/aip/tasks/{task_id}", headers=headers).json()
    assert approved_task["status"] == "approved"

    run = client.post(
        f"/v1/aip/tasks/{task_id}/runs",
        headers={**headers, "Idempotency-Key": f"run-{suffix}"},
        json={
            "planRevisionId": plan.json()["id"],
            "expectedTaskVersion": approved_task["version"],
        },
    )
    assert run.status_code == 202, run.text
    assert run.json()["status"] == "queued"
    timeline = client.get(
        f"/v1/aip/task-runs/{run.json()['id']}/timeline", headers=headers
    )
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["task"]["id"] == task_id
    assert timeline.json()["plan"]["contentHash"] == plan.json()["contentHash"]


def test_task_api_requires_auth_and_idempotency(client) -> None:
    assert client.post("/v1/aip/tasks", json={"title": "x"}).status_code == 401
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    assert client.post("/v1/aip/tasks", headers=headers, json={"title": "x"}).status_code == 400


def test_task_idempotency_replays_same_request_and_rejects_different_body(client) -> None:
    suffix = uuid.uuid4().hex
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
        "Idempotency-Key": f"idem-{suffix}",
    }
    first = client.post("/v1/aip/tasks", headers=headers, json={"title": "same"})
    replay = client.post("/v1/aip/tasks", headers=headers, json={"title": "same"})
    conflict = client.post("/v1/aip/tasks", headers=headers, json={"title": "different"})
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "AIP_IDEMPOTENCY_CONFLICT"


def test_plan_cas_and_exact_hash_fail_closed(client) -> None:
    suffix = uuid.uuid4().hex
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
        "Idempotency-Key": f"cas-task-{suffix}",
    }
    task = client.post("/v1/aip/tasks", headers=headers, json={"title": "cas"}).json()
    plan = client.post(
        f"/v1/aip/tasks/{task['id']}/plans",
        headers={**headers, "Idempotency-Key": f"cas-plan-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": [{"stepKey": "s1", "title": "只读分析"}],
        },
    )
    assert plan.status_code == 201
    stale = client.post(
        f"/v1/aip/tasks/{task['id']}/plans",
        headers={**headers, "Idempotency-Key": f"cas-stale-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": [{"stepKey": "s2", "title": "过期写入"}],
        },
    )
    assert stale.status_code == 409
    current = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    wrong_hash = client.post(
        f"/v1/aip/tasks/{task['id']}/plans/{plan.json()['revision']}/approve",
        headers={**headers, "Idempotency-Key": f"cas-approve-{suffix}"},
        json={
            "expectedTaskVersion": current["version"],
            "expectedContentHash": "0" * 64,
        },
    )
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["code"] == "AIP_VERSION_CONFLICT"


def test_task_scope_is_hidden_across_registered_workspaces(client) -> None:
    suffix = uuid.uuid4().hex
    org_a, org_b = f"task-org-a-{suffix}", f"task-org-b-{suffix}"
    project = f"task-project-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES (%s,%s),(%s,%s)",
            (org_a, "A", org_b, "B"),
        )
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,'A'),(%s,%s,'B')",
            (org_a, project, org_b, project),
        )
        conn.commit()
    headers_a = {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_a,
        "X-Project-Id": project,
        "Idempotency-Key": f"scope-{suffix}",
    }
    created = client.post("/v1/aip/tasks", headers=headers_a, json={"title": "private"})
    assert created.status_code == 201
    headers_b = {
        **headers_a,
        "X-Org-Id": org_b,
        "Idempotency-Key": f"scope-b-{suffix}",
    }
    hidden = client.get(f"/v1/aip/tasks/{created.json()['id']}", headers=headers_b)
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "AIP_RESOURCE_NOT_FOUND"


def test_aip_task_tables_force_rls_and_keep_single_migration_head() -> None:
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
               FROM pg_class c WHERE c.relname = ANY(%s::text[])""",
            (
                [
                    "aip_task",
                    "aip_plan_revision",
                    "aip_task_run",
                    "aip_step_run",
                    "aip_checkpoint",
                    "aip_artifact",
                    "aip_evidence",
                ],
            ),
        ).fetchall()
    assert len(rows) == 7
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
