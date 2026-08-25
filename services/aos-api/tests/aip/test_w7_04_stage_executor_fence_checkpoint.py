"""W7-04 canonical executor fencing, quiescence and resume acceptance."""
from __future__ import annotations

import uuid

import pytest

from aos_api.aip_task_store import AipTaskStore, AipTaskNotFound, AipTaskVersionConflict
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
ISOLATION_SCOPE = TenantScope("dev-org", "dev-project")


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _started_run(client, *, steps: list[dict] | None = None) -> tuple[dict, dict, dict[str, str]]:
    suffix = uuid.uuid4().hex
    headers = _headers(f"w7-04-task-{suffix}")
    task = client.post(
        "/v1/aip/tasks", headers=headers, json={"type": "media", "title": "W7-04 runtime"}
    ).json()
    plan = client.post(
        f"/v1/aip/tasks/{task['id']}/plans",
        headers={**headers, "Idempotency-Key": f"w7-04-plan-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": steps or [{
                "stepKey": "render",
                "title": "受控渲染",
                "checkpointPolicy": {"safePoint": "after_verify"},
                "retryPolicy": {"maxAttempts": 1},
                "compensationPolicy": {"mode": "reconcile_only"},
            }],
            "dependencies": [{"resourceType": "Capability", "resourceId": "media.render", "revision": 1}],
        },
    ).json()
    planning = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    approved = client.post(
        f"/v1/aip/tasks/{task['id']}/plans/{plan['revision']}/approve",
        headers={**headers, "Idempotency-Key": f"w7-04-approve-{suffix}"},
        json={"expectedTaskVersion": planning["version"], "expectedContentHash": plan["contentHash"]},
    )
    assert approved.status_code == 200, approved.text
    approved_task = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    run = client.post(
        f"/v1/aip/tasks/{task['id']}/runs",
        headers={**headers, "Idempotency-Key": f"w7-04-run-{suffix}"},
        json={"planRevisionId": plan["id"], "expectedTaskVersion": approved_task["version"]},
    ).json()
    started = client.post(
        f"/v1/aip/task-runs/{run['id']}/start",
        headers={**headers, "Idempotency-Key": f"w7-04-start-{suffix}"},
        json={"expectedRunVersion": run["version"], "expectedTaskVersion": approved_task["version"]},
    )
    assert started.status_code == 200, started.text
    return started.json()["task"], started.json()["run"], headers


def _record_success(store: AipTaskStore, lease) -> None:
    for phase, payload in (
        ("think", {"ready": True}),
        ("act", {"providerRequest": None}),
        ("verify", {"passed": True}),
        ("observe", {"artifactRefs": []}),
    ):
        store.record_step_phase(
            SCOPE, lease.step_run_id, lease.worker_id, lease.fence,
            "test-operator", phase, payload,
        )


def test_reclaim_advances_fence_and_old_worker_cannot_write(client) -> None:
    _, run, _ = _started_run(client)
    store = AipTaskStore()
    first = store.claim_step(SCOPE, run["id"], "render", "worker-a", lease_seconds=30)
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_step_run SET lease_expires_at=NOW()-INTERVAL '1 second'
               WHERE org_id=%s AND project_id=%s AND step_run_id=%s""",
            (*SCOPE.key, first.step_run_id),
        )
        conn.execute(
            """UPDATE aip_execution_assignment_head SET lease_expires_at=NOW()-INTERVAL '1 second'
               WHERE org_id=%s AND project_id=%s AND step_run_id=%s""",
            (*SCOPE.key, first.step_run_id),
        )
        conn.commit()
    second = store.claim_step(SCOPE, run["id"], "render", "worker-b", lease_seconds=30)
    assert second.fence == first.fence + 1
    assert second.input_hash == first.input_hash
    assert second.provider_request_fingerprint == first.provider_request_fingerprint
    with pytest.raises(AipTaskVersionConflict):
        store.record_step_phase(
            SCOPE, first.step_run_id, "worker-a", first.fence,
            "test-operator", "think", {"stale": True},
        )


def test_pause_quiesces_at_checkpoint_and_resume_records_reuse(client) -> None:
    task, run, headers = _started_run(client)
    store = AipTaskStore()
    lease = store.claim_step(SCOPE, run["id"], "render", "worker-a", lease_seconds=30)
    paused = client.post(
        f"/v1/aip/task-runs/{run['id']}/pause",
        headers={**headers, "Idempotency-Key": f"pause-{run['id']}"},
        json={"expectedRunVersion": run["version"], "expectedTaskVersion": task["version"], "reason": "operator pause"},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["run"]["status"] == "pausing"
    assert paused.json()["task"]["status"] == "paused"

    _record_success(store, lease)
    checkpoint_id = store.complete_step(
        SCOPE, lease.step_run_id, lease.worker_id, lease.fence, "test-operator"
    )
    timeline = store.timeline(SCOPE, run["id"])
    assert timeline.run.status.value == "paused"
    checkpoint = next(item for item in timeline.checkpoints if item["checkpoint_id"] == checkpoint_id)
    assert checkpoint["schema_version"] == 2
    assert checkpoint["attempt"] == 1
    assert checkpoint["input_hash"] == lease.input_hash
    assert checkpoint["provider_request_fingerprint"] == lease.provider_request_fingerprint
    assert checkpoint["state_hash"] and checkpoint["dependency_snapshot_hash"]
    assert checkpoint["checkpoint_policy"] == {"safePoint": "after_verify"}

    resumed = client.post(
        f"/v1/aip/task-runs/{run['id']}/resume",
        headers={**headers, "Idempotency-Key": f"resume-{run['id']}"},
        json={
            "expectedRunVersion": timeline.run.version,
            "expectedTaskVersion": timeline.task.version,
            "reason": "dependency snapshot unchanged",
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["run"]["status"] == "running"
    with connect(SCOPE) as conn:
        decision = conn.execute(
            """SELECT decision,reason_codes FROM aip_run_resume_decision_revision
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*SCOPE.key, run["id"]),
        ).fetchone()
    assert decision["decision"] == "reuse"
    assert decision["reason_codes"] == []


def test_pause_waits_for_every_active_step_to_reach_a_safe_point(client) -> None:
    task, run, headers = _started_run(
        client,
        steps=[
            {
                "stepKey": step_key,
                "title": title,
                "checkpointPolicy": {"safePoint": "after_verify"},
                "retryPolicy": {"maxAttempts": 1},
                "compensationPolicy": {"mode": "reconcile_only"},
            }
            for step_key, title in (("render", "受控渲染"), ("caption", "字幕封装"))
        ],
    )
    store = AipTaskStore()
    render = store.claim_step(SCOPE, run["id"], "render", "worker-a", lease_seconds=30)
    caption = store.claim_step(SCOPE, run["id"], "caption", "worker-b", lease_seconds=30)
    paused = client.post(
        f"/v1/aip/task-runs/{run['id']}/pause",
        headers={**headers, "Idempotency-Key": f"pause-multi-{run['id']}"},
        json={"expectedRunVersion": run["version"], "expectedTaskVersion": task["version"]},
    )
    assert paused.status_code == 200
    assert paused.json()["run"]["status"] == "pausing"

    _record_success(store, render)
    store.complete_step(SCOPE, render.step_run_id, render.worker_id, render.fence, "test-operator")
    assert store.timeline(SCOPE, run["id"]).run.status.value == "pausing"

    _record_success(store, caption)
    store.complete_step(SCOPE, caption.step_run_id, caption.worker_id, caption.fence, "test-operator")
    assert store.timeline(SCOPE, run["id"]).run.status.value == "paused"


def test_resume_dependency_drift_is_invalidated_and_tenant_isolated(client) -> None:
    task, run, headers = _started_run(client)
    paused = client.post(
        f"/v1/aip/task-runs/{run['id']}/pause",
        headers={**headers, "Idempotency-Key": f"pause-drift-{run['id']}"},
        json={"expectedRunVersion": run["version"], "expectedTaskVersion": task["version"]},
    )
    assert paused.status_code == 200
    assert paused.json()["run"]["status"] == "paused"
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_plan_revision SET dependencies='[{"resourceType":"Capability","resourceId":"media.render","revision":2}]'::jsonb
               WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (*SCOPE.key, run["planRevisionId"]),
        )
        conn.commit()
    response = client.post(
        f"/v1/aip/task-runs/{run['id']}/resume",
        headers={**headers, "Idempotency-Key": f"resume-drift-{run['id']}"},
        json={
            "expectedRunVersion": paused.json()["run"]["version"],
            "expectedTaskVersion": paused.json()["task"]["version"],
        },
    )
    assert response.status_code == 409
    replay = client.post(
        f"/v1/aip/task-runs/{run['id']}/resume",
        headers={**headers, "Idempotency-Key": f"resume-drift-{run['id']}"},
        json={
            "expectedRunVersion": paused.json()["run"]["version"],
            "expectedTaskVersion": paused.json()["task"]["version"],
        },
    )
    assert replay.status_code == 409
    with connect(SCOPE) as conn:
        decision = conn.execute(
            """SELECT decision,reason_codes FROM aip_run_resume_decision_revision
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*SCOPE.key, run["id"]),
        ).fetchone()
        decision_count = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_run_resume_decision_revision
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*SCOPE.key, run["id"]),
        ).fetchone()["count"]
    assert decision["decision"] == "invalidated"
    assert decision["reason_codes"] == ["DEPENDENCY_SNAPSHOT_DRIFTED"]
    assert decision_count == 1
    with pytest.raises(AipTaskNotFound):
        AipTaskStore().timeline(ISOLATION_SCOPE, run["id"])


def test_resume_recomputes_checkpoint_input_hash_and_fails_closed(client) -> None:
    task, run, headers = _started_run(client)
    store = AipTaskStore()
    lease = store.claim_step(SCOPE, run["id"], "render", "worker-a", lease_seconds=30)
    paused = client.post(
        f"/v1/aip/task-runs/{run['id']}/pause",
        headers={**headers, "Idempotency-Key": f"pause-input-drift-{run['id']}"},
        json={"expectedRunVersion": run["version"], "expectedTaskVersion": task["version"]},
    )
    assert paused.status_code == 200
    _record_success(store, lease)
    checkpoint_id = store.complete_step(
        SCOPE, lease.step_run_id, lease.worker_id, lease.fence, "test-operator"
    )
    timeline = store.timeline(SCOPE, run["id"])
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_checkpoint SET input_hash=%s
               WHERE org_id=%s AND project_id=%s AND checkpoint_id=%s""",
            ("f" * 64, *SCOPE.key, checkpoint_id),
        )
        conn.commit()
    response = client.post(
        f"/v1/aip/task-runs/{run['id']}/resume",
        headers={**headers, "Idempotency-Key": f"resume-input-drift-{run['id']}"},
        json={
            "expectedRunVersion": timeline.run.version,
            "expectedTaskVersion": timeline.task.version,
        },
    )
    assert response.status_code == 409
    with connect(SCOPE) as conn:
        decision = conn.execute(
            """SELECT decision,reason_codes,expected_input_hash,observed_input_hash
               FROM aip_run_resume_decision_revision
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*SCOPE.key, run["id"]),
        ).fetchone()
    assert decision["decision"] == "invalidated"
    assert decision["reason_codes"] == ["CHECKPOINT_INPUT_HASH_DRIFTED"]
    assert decision["expected_input_hash"] == "f" * 64
    assert decision["observed_input_hash"] == lease.input_hash


def test_quiesced_paused_run_can_be_cancelled(client) -> None:
    task, run, headers = _started_run(client)
    paused = client.post(
        f"/v1/aip/task-runs/{run['id']}/pause",
        headers={**headers, "Idempotency-Key": f"pause-cancel-{run['id']}"},
        json={
            "expectedRunVersion": run["version"],
            "expectedTaskVersion": task["version"],
        },
    )
    assert paused.status_code == 200
    cancelled = client.post(
        f"/v1/aip/task-runs/{run['id']}/cancel",
        headers={**headers, "Idempotency-Key": f"cancel-paused-{run['id']}"},
        json={
            "expectedRunVersion": paused.json()["run"]["version"],
            "expectedTaskVersion": paused.json()["task"]["version"],
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["run"]["status"] == "cancelled"
    assert cancelled.json()["task"]["status"] == "cancelled"
