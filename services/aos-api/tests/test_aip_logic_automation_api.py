"""HTTP contract tests for tenant-scoped Logic automation authority."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_logic_automation_models import LogicAutomationPolicy, LogicAutomationRun
from aos_api.aip_logic_automation_scheduler import run_due_logic_automations
from aos_api.aip_logic_automation_store import LogicAutomationStore
from aos_api.routers.aip_logic_automations import (
    get_logic_automation_store,
    get_logic_automation_task_service,
    router,
    summary_router,
)


def _policy(*, status: str = "active", trigger_type: str = "manual", schedule: str = "") -> LogicAutomationPolicy:
    now = datetime.now(UTC)
    return LogicAutomationPolicy(
        automation_id="logic-auto-1",
        graph_id="logic-1",
        publication_id="logic-pub-1",
        graph_revision=3,
        graph_hash="a" * 64,
        name="每日经营复盘",
        trigger_type=trigger_type,
        schedule=schedule,
        status=status,
        revision=2,
        actor="user:dev",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def automation_api(client):
    client.app.include_router(router)
    client.app.include_router(summary_router)
    policy = _policy()
    now = datetime.now(UTC)

    class FakeStore:
        record_args: dict | None = None

        def list(self, *_args):
            return [policy]

        def list_all(self, *_args):
            return [policy]

        def get(self, *_args):
            return policy

        def create(self, *_args):
            return policy

        def update(self, *_args):
            return policy.model_copy(update={"status": "paused", "revision": 3})

        def record_run(self, _org_id, _project_id, bound_policy, **kwargs):
            self.record_args = {"policy": bound_policy, **kwargs}
            return LogicAutomationRun(
                run_id="logic-auto-run-1",
                automation_id=bound_policy.automation_id,
                policy_revision=bound_policy.revision,
                trigger="manual",
                task_id=kwargs["task_id"],
                task_run_id=kwargs["task_run_id"],
                status="accepted",
                receipt_id="logic-auto-receipt-1",
                production_written=False,
                created_at=now,
                finished_at=now,
            )

        def list_runs(self, *_args):
            return []

    class FakeTaskStore:
        @staticmethod
        def get_task(_scope, _task_id):
            return SimpleNamespace(version=2)

    class FakeTasks:
        store = FakeTaskStore()
        calls: list[tuple[str, str]] = []

        @staticmethod
        def scope(_principal):
            return object()

        def create_task(self, _principal, key, _body):
            self.calls.append(("task", key))
            return SimpleNamespace(id="task-1", version=1)

        def create_plan(self, _principal, _task_id, key, _body):
            self.calls.append(("plan", key))
            return SimpleNamespace(revision=1, content_hash="b" * 64)

        def approve_plan(self, _principal, _task_id, _revision, _body):
            return SimpleNamespace(id="plan-revision-1")

        def create_run(self, _principal, _task_id, key, _body):
            self.calls.append(("run", key))
            return SimpleNamespace(id="task-run-1")

    store = FakeStore()
    tasks = FakeTasks()
    client.app.dependency_overrides[get_logic_automation_store] = lambda: store
    client.app.dependency_overrides[get_logic_automation_task_service] = lambda: tasks
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, store, tasks, headers
    client.app.dependency_overrides.pop(get_logic_automation_store, None)
    client.app.dependency_overrides.pop(get_logic_automation_task_service, None)


def test_policy_crud_and_history_are_tenant_scoped(automation_api) -> None:
    client, _store, _tasks, headers = automation_api
    listed = client.get("/v1/aip/logic/graphs/logic-1/automations", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    created = client.post(
        "/v1/aip/logic/graphs/logic-1/automations",
        headers=headers,
        json={"publication_id": "logic-pub-1", "name": "每日经营复盘"},
    )
    assert created.status_code == 201
    assert created.json()["graph_revision"] == 3

    paused = client.put(
        "/v1/aip/logic/graphs/logic-1/automations/logic-auto-1",
        headers=headers,
        json={"expected_revision": 2, "status": "paused"},
    )
    assert paused.status_code == 200
    assert paused.json()["revision"] == 3

    history = client.get(
        "/v1/aip/logic/graphs/logic-1/automations/logic-auto-1/runs",
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json() == {"items": [], "count": 0}

    tenant_summary = client.get(
        "/v1/aip/logic/automation-policies",
        headers=headers,
    )
    assert tenant_summary.status_code == 200
    assert tenant_summary.json()["count"] == 1


def test_manual_trigger_creates_canonical_task_plan_run_and_receipt(automation_api) -> None:
    client, store, tasks, headers = automation_api
    triggered = client.post(
        "/v1/aip/logic/graphs/logic-1/automations/logic-auto-1/trigger",
        headers={**headers, "Idempotency-Key": "manual-run-20260830-1"},
        json={},
    )
    assert triggered.status_code == 202
    assert triggered.json()["production_written"] is False
    assert triggered.json()["task_run_id"] == "task-run-1"
    assert store.record_args is not None
    assert store.record_args["policy"].automation_id == "logic-auto-1"
    assert store.record_args["idempotency_key"] == "manual-run-20260830-1"
    assert store.record_args["task_id"] == "task-1"
    assert store.record_args["task_run_id"] == "task-run-1"
    assert [kind for kind, _key in tasks.calls] == ["task", "plan", "run"]
    assert len({key for _kind, key in tasks.calls}) == 3


def test_manual_trigger_requires_explicit_idempotency_key(automation_api) -> None:
    client, _store, _tasks, headers = automation_api
    response = client.post(
        "/v1/aip/logic/graphs/logic-1/automations/logic-auto-1/trigger",
        headers=headers,
        json={},
    )
    assert response.status_code == 400


def test_cron_and_event_rules_require_explicit_trigger_configuration(automation_api) -> None:
    client, _store, _tasks, headers = automation_api
    missing = client.post(
        "/v1/aip/logic/graphs/logic-1/automations",
        headers=headers,
        json={
            "publication_id": "logic-pub-1",
            "name": "工作日经营复盘",
            "trigger_type": "cron",
            "schedule": "",
        },
    )
    assert missing.status_code in {400, 422}

    configured = client.post(
        "/v1/aip/logic/graphs/logic-1/automations",
        headers=headers,
        json={
            "publication_id": "logic-pub-1",
            "name": "工作日经营复盘",
            "trigger_type": "cron",
            "schedule": "0 9 * * 1-5",
        },
    )
    assert configured.status_code == 201

    invalid = client.post(
        "/v1/aip/logic/graphs/logic-1/automations",
        headers=headers,
        json={
            "publication_id": "logic-pub-1",
            "name": "错误定时规则",
            "trigger_type": "cron",
            "schedule": "61 25 * * *",
        },
    )
    assert invalid.status_code in {400, 422}


def test_cron_scheduler_matches_minute_and_reuses_deterministic_idempotency(monkeypatch) -> None:
    due = _policy(trigger_type="cron", schedule="*/15 9 * * 1-5")

    class FakeStore:
        def list_active_cron_targets(self):
            return [("org-org", "dev-project", due)]

    calls: list[dict] = []

    def fake_dispatch(principal, policy, store, tasks, **kwargs):
        calls.append({"principal": principal, "policy": policy, **kwargs})

    monkeypatch.setattr(
        "aos_api.aip_logic_automation_scheduler.dispatch_logic_automation",
        fake_dispatch,
    )
    moment = datetime(2026, 8, 31, 9, 30, tzinfo=UTC)
    first = run_due_logic_automations(
        now=moment,
        store=FakeStore(),
        task_service_factory=lambda: object(),
    )
    second = run_due_logic_automations(
        now=moment,
        store=FakeStore(),
        task_service_factory=lambda: object(),
    )
    assert first == second == {"matched": 1, "accepted": 1, "failed": 0}
    assert [call["request_key"] for call in calls] == ["cron:202608310930"] * 2
    assert calls[0]["trigger"] == "cron"
    assert calls[0]["principal"].org_id == "org-org"

    not_due = run_due_logic_automations(
        now=datetime(2026, 8, 31, 9, 31, tzinfo=UTC),
        store=FakeStore(),
        task_service_factory=lambda: object(),
    )
    assert not_due == {"matched": 0, "accepted": 0, "failed": 0}


def test_store_projection_hides_tenant_and_idempotency_columns() -> None:
    now = datetime.now(UTC)
    run = LogicAutomationStore._run(
        {
            "org_id": "org-org",
            "project_id": "dev-project",
            "run_id": "logic-auto-run-1",
            "automation_id": "logic-auto-1",
            "policy_revision": 2,
            "trigger": "manual",
            "task_id": "task-1",
            "task_run_id": "task-run-1",
            "status": "accepted",
            "receipt_id": "receipt-1",
            "production_written": False,
            "idempotency_key": "manual-1",
            "created_at": now,
            "finished_at": now,
        }
    )
    assert run.run_id == "logic-auto-run-1"
    assert run.production_written is False
