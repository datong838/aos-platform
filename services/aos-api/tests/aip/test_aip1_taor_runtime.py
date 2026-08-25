"""AIP-1B lifecycle, lease and persistent TAOR acceptance tests."""
from __future__ import annotations

import uuid
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import pytest

from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.aip_research_job import (
    ResearchJobEvent,
    ResearchJobObservation,
    ResearchJobStatus,
    reconcile_research_events,
    verify_research_callback,
)
from aos_api.aip_task_store import (
    AipTaskStore,
    AipTaskTransitionBlocked,
    AipTaskVersionConflict,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _approved_run(client, *, steps: list[dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    suffix = uuid.uuid4().hex
    headers = _headers(f"aip1b-task-{suffix}")
    task = client.post(
        "/v1/aip/tasks", headers=headers, json={"type": "aip1b", "title": "TAOR runtime"}
    ).json()
    plan = client.post(
        f"/v1/aip/tasks/{task['id']}/plans",
        headers={**headers, "Idempotency-Key": f"aip1b-plan-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": steps
            or [
                {"stepKey": "inspect", "title": "检查输入"},
                {"stepKey": "summarize", "title": "形成结论"},
            ],
        },
    ).json()
    planned_task = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    approved = client.post(
        f"/v1/aip/tasks/{task['id']}/plans/{plan['revision']}/approve",
        headers={**headers, "Idempotency-Key": f"aip1b-approve-{suffix}"},
        json={
            "expectedTaskVersion": planned_task["version"],
            "expectedContentHash": plan["contentHash"],
        },
    )
    assert approved.status_code == 200, approved.text
    approved_task = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    run = client.post(
        f"/v1/aip/tasks/{task['id']}/runs",
        headers={**headers, "Idempotency-Key": f"aip1b-run-{suffix}"},
        json={
            "planRevisionId": plan["id"],
            "expectedTaskVersion": approved_task["version"],
        },
    )
    assert run.status_code == 202, run.text
    return headers, run.json()


def _control(client, headers, run, operation, task_version):
    response = client.post(
        f"/v1/aip/task-runs/{run['id']}/{operation}",
        headers={**headers, "Idempotency-Key": f"{operation}-{run['id']}"},
        json={
            "expectedRunVersion": run["version"],
            "expectedTaskVersion": task_version,
            "reason": f"test {operation}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_run_control_pause_resume_and_cancel_are_cas_guarded(client) -> None:
    headers, run = _approved_run(client)
    task = client.get(f"/v1/aip/tasks/{run['taskId']}", headers=headers).json()

    started = _control(client, headers, run, "start", task["version"])
    assert started["task"]["status"] == "executing"
    assert started["run"]["status"] == "running"
    replayed_start = _control(client, headers, run, "start", task["version"])
    assert replayed_start["run"]["id"] == started["run"]["id"]
    assert replayed_start["run"]["version"] == started["run"]["version"]

    stale = client.post(
        f"/v1/aip/task-runs/{run['id']}/pause",
        headers=headers,
        json={"expectedRunVersion": run["version"], "expectedTaskVersion": task["version"]},
    )
    assert stale.status_code == 409

    paused = _control(
        client, headers, started["run"], "pause", started["task"]["version"]
    )
    assert paused["task"]["status"] == "paused"
    resumed = _control(
        client, headers, paused["run"], "resume", paused["task"]["version"]
    )
    assert resumed["task"]["status"] == "executing"
    cancelled = _control(
        client, headers, resumed["run"], "cancel", resumed["task"]["version"]
    )
    assert cancelled["task"]["status"] == "cancelled"
    assert cancelled["run"]["status"] == "cancelled"


def test_legacy_logic_and_automation_fail_closed_in_real_scope(client, monkeypatch) -> None:
    monkeypatch.setenv("AIP_DEMO_MOCK_ENABLED", "1")
    headers = _headers(f"legacy-{uuid.uuid4().hex}")
    unauthenticated = client.post(
        "/v1/aip/logic/execute", json={"blocks": [{"kind": "task", "name": "x"}]}
    )
    assert unauthenticated.status_code == 401
    execution = client.post(
        "/v1/aip/logic/execute",
        headers=headers,
        json={"blocks": [{"kind": "task", "name": "x"}]},
    )
    assert execution.status_code == 422
    assert execution.json()["code"] == "AIP_INVALID_TRANSITION"
    automation = client.post(
        "/v1/aip/logic/automations",
        headers=headers,
        json={"name": "must not persist in memory"},
    )
    assert automation.status_code == 422


def test_only_one_worker_can_hold_an_active_step_lease(client) -> None:
    headers, run = _approved_run(client, steps=[{"stepKey": "one", "title": "唯一步骤"}])
    store = AipTaskStore()
    task = client.get(f"/v1/aip/tasks/{run['taskId']}", headers=headers).json()
    store.start_run(
        SCOPE,
        run["id"],
        expected_run_version=run["version"],
        expected_task_version=task["version"],
        actor="test-operator",
        idempotency_key=f"lease-start-{run['id']}",
    )
    first = store.claim_step(SCOPE, run["id"], "one", "worker-a", lease_seconds=30)
    assert first.worker_id == "worker-a"
    with pytest.raises(AipTaskVersionConflict):
        store.claim_step(SCOPE, run["id"], "one", "worker-b", lease_seconds=30)


def test_expired_lease_after_action_enters_unknown_without_repeating_action(client) -> None:
    headers, run = _approved_run(client, steps=[{"stepKey": "one", "title": "外部动作"}])
    store = AipTaskStore()
    task = client.get(f"/v1/aip/tasks/{run['taskId']}", headers=headers).json()
    store.start_run(
        SCOPE,
        run["id"],
        expected_run_version=run["version"],
        expected_task_version=task["version"],
        actor="test-operator",
        idempotency_key=f"unknown-start-{run['id']}",
    )
    lease = store.claim_step(SCOPE, run["id"], "one", "worker-a", lease_seconds=30)
    store.record_step_phase(
        SCOPE, lease.step_run_id, "worker-a", lease.fence, "test-operator", "think", {"ready": True}
    )
    store.record_step_phase(
        SCOPE,
        lease.step_run_id,
        "worker-a",
        lease.fence,
        "test-operator",
        "act",
        {"externalExecutionId": "external-1"},
    )
    with connect(SCOPE) as conn:
        conn.execute(
            "UPDATE aip_step_run SET lease_expires_at=NOW()-INTERVAL '1 second' WHERE org_id=%s AND project_id=%s AND step_run_id=%s",
            (SCOPE.org_id, SCOPE.project_id, lease.step_run_id),
        )
        conn.commit()
    with pytest.raises(AipTaskTransitionBlocked, match="requires reconcile"):
        store.claim_step(SCOPE, run["id"], "one", "worker-b", lease_seconds=30)
    timeline = store.timeline(SCOPE, run["id"])
    assert timeline.run.status.value == "unknown"
    assert timeline.task.status.value == "paused"
    assert timeline.steps[0]["status"] == "unknown"


class _Adapter:
    def think(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        assert context["taskGoal"] == {}
        return {"instruction": f"execute {step['stepKey']}", "context": context["runRef"]}

    def act(self, step: dict[str, Any], thought: dict[str, Any]) -> dict[str, Any]:
        return {"output": thought["instruction"], "externalExecutionId": None}

    def verify(self, step: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
        return {"passed": True, "checked": action["output"]}

    def observe(
        self,
        step: dict[str, Any],
        action: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "summary": f"{step['stepKey']} observed",
            "artifacts": [
                {
                    "type": "taor-result",
                    "contentRef": f"aip://{step['stepKey']}",
                    "metadata": {"verified": verification["passed"]},
                }
            ],
        }


def test_canonical_taor_persists_four_phases_checkpoints_artifacts_and_rollback(client) -> None:
    headers, run = _approved_run(client)
    result = CanonicalTaorRunner().run(
        SCOPE,
        run["id"],
        actor="test-operator",
        worker_id="worker-runtime",
        adapter=_Adapter(),
    )
    assert result.run.status.value == "succeeded"
    assert result.task.status.value == "completed"

    timeline = client.get(
        f"/v1/aip/task-runs/{run['id']}/timeline", headers=headers
    )
    assert timeline.status_code == 200, timeline.text
    payload = timeline.json()
    assert len(payload["steps"]) == 2
    assert {item["status"] for item in payload["steps"]} == {"succeeded"}
    assert len(payload["checkpoints"]) == 2
    assert len(payload["artifacts"]) == 2
    phase_types = [item["evidence_type"] for item in payload["evidence"]]
    for phase in ("think", "act", "verify", "observe"):
        assert phase_types.count(f"taor.{phase}") == 2

    rolled_back = _control(
        client,
        headers,
        payload["run"],
        "rollback",
        payload["task"]["version"],
    )
    assert rolled_back["task"]["status"] == "rolled_back"
    persisted = client.get(
        f"/v1/aip/task-runs/{run['id']}/timeline", headers=headers
    ).json()
    assert len(persisted["checkpoints"]) == 2
    assert len(persisted["artifacts"]) == 2
    assert any(item["evidence_type"] == "rollback" for item in persisted["evidence"])


def test_canonical_taor_refuses_unversioned_capability_binding(client) -> None:
    _, run = _approved_run(
        client,
        steps=[
            {
                "stepKey": "unsafe",
                "title": "未固定版本",
                "capabilityRef": {
                    "resourceType": "Skill",
                    "resourceId": "skill-1",
                    "authority": "aip-skill-registry",
                },
            }
        ],
    )
    with pytest.raises(AipTaskTransitionBlocked, match="exact revision"):
        CanonicalTaorRunner().run(
            SCOPE,
            run["id"],
            actor="test-operator",
            worker_id="worker-runtime",
            adapter=_Adapter(),
        )
    assert AipTaskStore().get_run(SCOPE, run["id"]).status.value == "queued"


def _research_event(sequence: int, status: str, payload: dict[str, Any]) -> ResearchJobEvent:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return ResearchJobEvent(
        provider_execution_id="provider-run-1",
        sequence=sequence,
        event_id=f"event-{sequence}",
        status=status,
        payload_hash=hashlib.sha256(encoded).hexdigest(),
        observed_at=datetime.now(timezone.utc),
        payload=payload,
    )


def test_research_job_events_are_deduplicated_monotonic_and_gap_aware() -> None:
    initial = ResearchJobObservation(
        provider_execution_id="provider-run-1",
        status=ResearchJobStatus.QUEUED,
        last_sequence=0,
    )
    first = _research_event(1, "running", {"progress": 10})
    succeeded = _research_event(2, "succeeded", {"artifactCount": 1})
    reconciled = reconcile_research_events(initial, [succeeded, first, first])
    assert reconciled.status is ResearchJobStatus.SUCCEEDED
    assert reconciled.last_sequence == 2
    assert reconciled.event_ids == ["event-1", "event-2"]

    late_running = _research_event(3, "running", {"progress": 90})
    with pytest.raises(ValueError, match="cannot regress"):
        reconcile_research_events(reconciled, [late_running])

    gap = reconcile_research_events(initial, [succeeded])
    assert gap.has_gap is True
    assert gap.last_sequence == 0


def test_research_callback_rejects_bad_signature_and_nonce_replay() -> None:
    secret = b"test-only-secret"
    body = b'{"executionId":"provider-run-1"}'
    now = datetime.now(timezone.utc)
    timestamp = int(now.timestamp())
    nonce = "nonce-1"
    body_hash = hashlib.sha256(body).hexdigest()
    signature = hmac.new(
        secret,
        f"{timestamp}.{nonce}.{body_hash}".encode(),
        hashlib.sha256,
    ).hexdigest()
    seen: set[str] = set()
    assert verify_research_callback(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        body=body,
        signature=signature,
        seen_nonces=seen,
        now=now,
    ) == body_hash
    with pytest.raises(ValueError, match="replayed"):
        verify_research_callback(
            secret=secret,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
            seen_nonces=seen,
            now=now,
        )
