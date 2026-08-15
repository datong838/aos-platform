"""W2-02 Task Cockpit core read contract and tenant-bound cursor tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aos_api.auth import Principal, require_principal
from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.ecommerce_workshop_task_cockpit import (
    EcommerceWorkshopTaskCockpit,
    TaskCockpitPersistenceError,
    _decode_cursor,
)
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitCoreEnvelope,
)
from aos_api.errors import ApiError, register_exception_handlers
from aos_api.public_contracts import TaskStatus
from aos_api.routers import ecommerce_workshop
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)


def _row(*, suffix: str, updated_at: datetime, with_run: bool = True) -> dict[str, Any]:
    return {
        "task_id": f"task-{suffix}",
        "task_type": "ecommerce.operation-review",
        "title": f"Task {suffix}",
        "task_status": "cancelled",
        "priority": 30,
        "task_version": 2,
        "current_plan_revision_id": f"plan-{suffix}",
        "task_updated_at": updated_at,
        "run_id": f"run-{suffix}" if with_run else None,
        "plan_revision_id": f"plan-{suffix}" if with_run else None,
        "run_status": "cancelled" if with_run else None,
        "run_version": 3 if with_run else None,
        "started_at": updated_at - timedelta(minutes=2) if with_run else None,
        "finished_at": updated_at - timedelta(minutes=1) if with_run else None,
        "run_updated_at": updated_at if with_run else None,
    }


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class ConnectionQueue:
    def __init__(self, *row_sets: list[dict[str, Any]]):
        self.row_sets = list(row_sets)
        self.connections: list[FakeConnection] = []

    @contextmanager
    def connect(self):
        connection = FakeConnection(self.row_sets.pop(0))
        self.connections.append(connection)
        yield connection


def test_core_read_is_degraded_read_only_and_uses_stable_keyset_cursor() -> None:
    first_rows = [
        _row(suffix="2", updated_at=NOW - timedelta(minutes=1)),
        _row(suffix="1", updated_at=NOW - timedelta(minutes=2), with_run=False),
    ]
    second_rows = [first_rows[1]]
    queue = ConnectionQueue(first_rows, second_rows)
    cockpit = EcommerceWorkshopTaskCockpit(
        connect_factory=queue.connect,
        clock=lambda: NOW,
    )

    first = cockpit.read_core(
        org_id="org-org",
        project_id="dev-project",
        status=TaskStatus.CANCELLED,
        limit=1,
        cursor=None,
    )
    assert first.readiness == "degraded"
    assert first.page.count == 1
    assert first.page.has_more is True
    assert first.page.next_cursor
    assert len(first.blockers) == 3
    assert first.items[0].run is not None

    second = cockpit.read_core(
        org_id="org-org",
        project_id="dev-project",
        status=TaskStatus.CANCELLED,
        limit=1,
        cursor=first.page.next_cursor,
    )
    assert second.task_cutoff == first.task_cutoff
    assert second.page.has_more is False
    assert second.items[0].task_id == "task-1"
    assert second.items[0].run is None
    assert {first.items[0].task_id}.isdisjoint(
        {item.task_id for item in second.items}
    )

    for connection in queue.connections:
        sql = " ".join(call[0] for call in connection.calls).upper()
        assert "REPEATABLE READ READ ONLY" in sql
        assert "SET LOCAL ROLE AOS_RUNTIME" in sql
        assert not any(token in sql for token in ("INSERT ", "UPDATE ", "DELETE "))
    page_query, page_params = queue.connections[1].calls[-1]
    assert "(t.updated_at,t.task_id)<(%s,%s)" in page_query
    assert page_params is not None
    assert page_params[0] == first.task_cutoff
    assert page_params[1:3] == ("org-org", "dev-project")
    assert page_params[-3:-1] == (
        first_rows[0]["task_updated_at"],
        first_rows[0]["task_id"],
    )


def test_cursor_rejects_tampering_cross_tenant_and_filter_reuse() -> None:
    queue = ConnectionQueue(
        [
            _row(suffix="2", updated_at=NOW - timedelta(minutes=1)),
            _row(suffix="1", updated_at=NOW - timedelta(minutes=2)),
        ]
    )
    cockpit = EcommerceWorkshopTaskCockpit(
        connect_factory=queue.connect,
        clock=lambda: NOW,
    )
    page = cockpit.read_core(
        org_id="org-org",
        project_id="dev-project",
        status=None,
        limit=1,
        cursor=None,
    )
    cursor = page.page.next_cursor
    assert cursor is not None

    for candidate, scope, status in (
        (
            cursor[:-1] + ("A" if cursor[-1] != "A" else "B"),
            TenantScope("org-org", "dev-project"),
            None,
        ),
        (cursor, TenantScope("dev-org", "dev-project"), None),
        (cursor, TenantScope("org-org", "dev-project"), TaskStatus.CANCELLED),
    ):
        with pytest.raises(ApiError) as captured:
            _decode_cursor(candidate, scope=scope, status=status)
        assert captured.value.code == "TASK_COCKPIT_CURSOR_INVALID"
        assert captured.value.status_code == 400


def test_contract_rejects_unknown_fields_naive_times_and_count_drift() -> None:
    base = {
        "schemaVersion": "aos.ecommerce-workshop.task-cockpit/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "evaluatedAt": NOW,
        "taskCutoff": NOW,
        "readiness": "degraded",
        "blockers": [
            {
                "code": f"BLOCKER_{index}",
                "severity": "warning",
                "dependency": "dependency",
                "requiredAction": "wait",
            }
            for index in range(3)
        ],
        "items": [],
        "page": {"limit": 50, "count": 0, "hasMore": False, "nextCursor": None},
    }
    TaskCockpitCoreEnvelope.model_validate(base)

    with pytest.raises(ValidationError):
        TaskCockpitCoreEnvelope.model_validate({**base, "unexpected": True})
    with pytest.raises(ValidationError):
        TaskCockpitCoreEnvelope.model_validate(
            {**base, "evaluatedAt": datetime(2026, 8, 15, 10, 0)}
        )
    with pytest.raises(ValidationError):
        TaskCockpitCoreEnvelope.model_validate(
            {**base, "page": {**base["page"], "count": 1}}
        )


class FakeCockpit:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def read_core(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        return TaskCockpitCoreEnvelope.model_validate(
            {
                "tenant": {
                    "orgId": kwargs["org_id"],
                    "projectId": kwargs["project_id"],
                },
                "evaluatedAt": NOW,
                "taskCutoff": NOW,
                "readiness": "degraded",
                "blockers": [
                    {
                        "code": f"BLOCKER_{index}",
                        "severity": "warning",
                        "dependency": "dependency",
                        "requiredAction": "wait",
                    }
                    for index in range(3)
                ],
                "items": [],
                "page": {
                    "limit": kwargs["limit"],
                    "count": 0,
                    "hasMore": False,
                    "nextCursor": None,
                },
            }
        )


class FakeCatalog:
    def __init__(self, *, installed: bool = True):
        self.installed = installed
        self.calls: list[dict[str, Any]] = []

    def get_readiness(self, **kwargs):
        self.calls.append(kwargs)
        if not self.installed:
            raise AssetNotFoundError("Workshop module is not installed")
        return object()


def _client(
    cockpit: FakeCockpit, catalog: FakeCatalog | None = None
) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[
        ecommerce_workshop.get_ecommerce_workshop_task_cockpit
    ] = lambda: cockpit
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = (
        lambda: catalog or FakeCatalog()
    )
    return TestClient(app, raise_server_exceptions=False)


def test_api_uses_principal_scope_rejects_injection_and_maps_dependency_failure() -> None:
    cockpit = FakeCockpit()
    catalog = FakeCatalog()
    with _client(cockpit, catalog) as client:
        response = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit?status=cancelled&limit=20"
        )
        assert response.status_code == 200
        assert response.json()["tenant"] == {
            "orgId": "org-org",
            "projectId": "dev-project",
        }
        injected = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit?orgId=dev-org"
        )
        assert injected.status_code == 400
        assert injected.json()["code"] == "VALIDATION"
        duplicated = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit?limit=1&limit=2"
        )
        assert duplicated.status_code == 400
        assert duplicated.json()["code"] == "VALIDATION"

    assert cockpit.calls == [
        {
            "org_id": "org-org",
            "project_id": "dev-project",
            "status": TaskStatus.CANCELLED,
            "limit": 20,
            "cursor": None,
        }
    ]
    assert catalog.calls == [
        {
            "module_id": "ecommerce.task-cockpit",
            "org_id": "org-org",
            "project_id": "dev-project",
            "roles": ["operator"],
            "markings": ["public"],
        }
    ]

    with _client(FakeCockpit(fail=True)) as client:
        failed = client.get("/v1/ecommerce-workshop/views/task-cockpit")
        assert failed.status_code == 503
        assert failed.json()["code"] == "TASK_COCKPIT_DEPENDENCY_UNAVAILABLE"
        assert failed.json()["message"] == (
            "Task Cockpit read dependency is unavailable"
        )
        assert "sensitive database detail" not in failed.text


def test_api_fails_closed_when_task_cockpit_module_is_not_installed() -> None:
    cockpit = FakeCockpit()
    with _client(cockpit, FakeCatalog(installed=False)) as client:
        response = client.get("/v1/ecommerce-workshop/views/task-cockpit")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert cockpit.calls == []
