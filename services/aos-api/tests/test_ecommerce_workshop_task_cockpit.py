"""W2-02 Task Cockpit core read contract and tenant-bound cursor tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    TaskCockpitCheckpointPageEnvelope,
    TaskCockpitCoreEnvelope,
    TaskCockpitStepPageEnvelope,
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
        "task_created_at": updated_at - timedelta(hours=1),
        "task_updated_at": updated_at,
        "run_id": f"run-{suffix}" if with_run else None,
        "plan_revision_id": f"plan-{suffix}" if with_run else None,
        "run_status": "cancelled" if with_run else None,
        "run_version": 3 if with_run else None,
        "started_at": updated_at - timedelta(minutes=2) if with_run else None,
        "finished_at": updated_at - timedelta(minutes=1) if with_run else None,
        "run_created_at": updated_at - timedelta(minutes=3) if with_run else None,
        "run_updated_at": updated_at if with_run else None,
    }


class FakeConnection:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        snapshot_hash: str = "a" * 32,
        run_exists: bool = True,
    ):
        self.rows = rows
        self.snapshot_hash = snapshot_hash
        self.run_exists = run_exists
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def fetchone(self) -> dict[str, Any] | None:
        sql = self.calls[-1][0]
        if "AS snapshot_hash" in sql:
            return {"snapshot_hash": self.snapshot_hash}
        if "SELECT 1 FROM aip_task_run" in sql:
            return {"present": 1} if self.run_exists else None
        raise AssertionError(f"unexpected fetchone query: {sql}")


class ConnectionQueue:
    def __init__(
        self,
        *row_sets: list[dict[str, Any]],
        snapshot_hashes: list[str] | None = None,
        run_exists: bool = True,
    ):
        self.row_sets = list(row_sets)
        self.snapshot_hashes = snapshot_hashes or ["a" * 32] * len(row_sets)
        self.run_exists = run_exists
        self.connections: list[FakeConnection] = []

    @contextmanager
    def connect(self):
        connection = FakeConnection(
            self.row_sets.pop(0),
            snapshot_hash=self.snapshot_hashes.pop(0),
            run_exists=self.run_exists,
        )
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
    assert first.state_consistency == "current_state_per_page"
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
    assert "(t.created_at,t.task_id)<(%s,%s)" in page_query
    assert page_params is not None
    assert page_params[0] == first.task_cutoff
    assert page_params[1:3] == ("org-org", "dev-project")
    assert page_params[-3:-1] == (
        first_rows[0]["task_created_at"],
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


def test_core_cursor_fails_stale_instead_of_drifting_across_mutable_status() -> None:
    rows = [
        _row(suffix="2", updated_at=NOW - timedelta(minutes=1)),
        _row(suffix="1", updated_at=NOW - timedelta(minutes=2)),
    ]
    queue = ConnectionQueue(
        rows,
        rows[1:],
        snapshot_hashes=["a" * 32, "b" * 32],
    )
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
    with pytest.raises(ApiError) as captured:
        cockpit.read_core(
            org_id="org-org",
            project_id="dev-project",
            status=TaskStatus.CANCELLED,
            limit=1,
            cursor=first.page.next_cursor,
        )
    assert captured.value.code == "TASK_COCKPIT_CURSOR_STALE"
    assert captured.value.status_code == 409


def _step_row(*, suffix: str, created_at: datetime) -> dict[str, Any]:
    return {
        "step_run_id": f"step-{suffix}",
        "step_key": f"stage-{suffix}",
        "attempt": 1,
        "status": "succeeded",
        "token_count": 12,
        "cost_amount": Decimal("0.125"),
        "has_input_refs": True,
        "has_output_refs": True,
        "has_error": False,
        "created_at": created_at,
        "updated_at": created_at + timedelta(minutes=1),
    }


def _checkpoint_row(*, suffix: str, sequence: int) -> dict[str, Any]:
    return {
        "checkpoint_id": f"checkpoint-{suffix}",
        "sequence": sequence,
        "schema_version": 1,
        "step_key": f"stage-{suffix}",
        "state_hash": "a" * 64,
        "artifact_count": sequence,
        "created_at": NOW - timedelta(minutes=10 - sequence),
    }


def test_step_and_checkpoint_pages_are_typed_bounded_and_independently_cursorized() -> None:
    steps = [
        _step_row(suffix="1", created_at=NOW - timedelta(minutes=9)),
        _step_row(suffix="2", created_at=NOW - timedelta(minutes=8)),
    ]
    checkpoints = [
        _checkpoint_row(suffix="1", sequence=1),
        _checkpoint_row(suffix="2", sequence=2),
    ]
    queue = ConnectionQueue(steps, steps[1:], checkpoints, checkpoints[1:])
    cockpit = EcommerceWorkshopTaskCockpit(
        connect_factory=queue.connect,
        clock=lambda: NOW,
    )

    first_steps = cockpit.read_steps(
        org_id="org-org",
        project_id="dev-project",
        run_id="run-1",
        limit=1,
        cursor=None,
    )
    second_steps = cockpit.read_steps(
        org_id="org-org",
        project_id="dev-project",
        run_id="run-1",
        limit=1,
        cursor=first_steps.page.next_cursor,
    )
    assert first_steps.state_consistency == "current_state_per_page"
    assert first_steps.items[0].step_run_id == "step-1"
    assert first_steps.items[0].cost_amount == Decimal("0.125")
    assert second_steps.items[0].step_run_id == "step-2"
    assert second_steps.page.has_more is False

    first_checkpoints = cockpit.read_checkpoints(
        org_id="org-org",
        project_id="dev-project",
        run_id="run-1",
        limit=1,
        cursor=None,
    )
    second_checkpoints = cockpit.read_checkpoints(
        org_id="org-org",
        project_id="dev-project",
        run_id="run-1",
        limit=1,
        cursor=first_checkpoints.page.next_cursor,
    )
    assert first_checkpoints.items[0].sequence == 1
    assert second_checkpoints.items[0].sequence == 2
    assert second_checkpoints.page.has_more is False

    step_sql = queue.connections[1].calls[-1][0]
    checkpoint_sql = queue.connections[3].calls[-1][0]
    assert "(created_at,step_run_id)>(%s,%s)" in step_sql
    assert "(sequence,checkpoint_id)>(%s,%s)" in checkpoint_sql
    assert "input_refs" not in first_steps.model_dump(mode="json", by_alias=True)[
        "items"
    ][0]
    assert "artifactRefs" not in first_checkpoints.model_dump(
        mode="json", by_alias=True
    )["items"][0]


def test_detail_cursor_rejects_cross_kind_and_missing_run_is_not_an_empty_page() -> None:
    steps = [
        _step_row(suffix="1", created_at=NOW - timedelta(minutes=9)),
        _step_row(suffix="2", created_at=NOW - timedelta(minutes=8)),
    ]
    cockpit = EcommerceWorkshopTaskCockpit(
        connect_factory=ConnectionQueue(steps).connect,
        clock=lambda: NOW,
    )
    page = cockpit.read_steps(
        org_id="org-org",
        project_id="dev-project",
        run_id="run-1",
        limit=1,
        cursor=None,
    )
    with pytest.raises(ApiError) as captured:
        EcommerceWorkshopTaskCockpit(
            connect_factory=ConnectionQueue([], run_exists=True).connect,
            clock=lambda: NOW,
        ).read_checkpoints(
            org_id="org-org",
            project_id="dev-project",
            run_id="run-1",
            limit=1,
            cursor=page.page.next_cursor,
        )
    assert captured.value.code == "TASK_COCKPIT_CURSOR_INVALID"

    for org_id, run_id in (("dev-org", "run-1"), ("org-org", "run-2")):
        with pytest.raises(ApiError) as captured:
            EcommerceWorkshopTaskCockpit(
                connect_factory=ConnectionQueue([]).connect,
                clock=lambda: NOW,
            ).read_steps(
                org_id=org_id,
                project_id="dev-project",
                run_id=run_id,
                limit=1,
                cursor=page.page.next_cursor,
            )
        assert captured.value.code == "TASK_COCKPIT_CURSOR_INVALID"

    missing = EcommerceWorkshopTaskCockpit(
        connect_factory=ConnectionQueue([], run_exists=False).connect,
        clock=lambda: NOW,
    )
    with pytest.raises(ApiError) as captured:
        missing.read_steps(
            org_id="org-org",
            project_id="dev-project",
            run_id="run-missing",
            limit=10,
            cursor=None,
        )
    assert captured.value.code == "TASK_COCKPIT_RUN_NOT_FOUND"
    assert captured.value.status_code == 404


def test_step_cursor_fails_stale_when_current_step_state_changes() -> None:
    rows = [
        _step_row(suffix="1", created_at=NOW - timedelta(minutes=9)),
        _step_row(suffix="2", created_at=NOW - timedelta(minutes=8)),
    ]
    queue = ConnectionQueue(
        rows,
        rows[1:],
        snapshot_hashes=["a" * 32, "b" * 32],
    )
    cockpit = EcommerceWorkshopTaskCockpit(
        connect_factory=queue.connect,
        clock=lambda: NOW,
    )
    first = cockpit.read_steps(
        org_id="org-org",
        project_id="dev-project",
        run_id="run-1",
        limit=1,
        cursor=None,
    )
    with pytest.raises(ApiError) as captured:
        cockpit.read_steps(
            org_id="org-org",
            project_id="dev-project",
            run_id="run-1",
            limit=1,
            cursor=first.page.next_cursor,
        )
    assert captured.value.code == "TASK_COCKPIT_CURSOR_STALE"


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
        self.detail_calls: list[tuple[str, dict[str, Any]]] = []

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

    def read_steps(self, **kwargs):
        self.detail_calls.append(("steps", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        return TaskCockpitStepPageEnvelope.model_validate(
            {
                "tenant": {
                    "orgId": kwargs["org_id"],
                    "projectId": kwargs["project_id"],
                },
                "runId": kwargs["run_id"],
                "evaluatedAt": NOW,
                "membershipCutoff": NOW,
                "items": [],
                "page": {
                    "limit": kwargs["limit"],
                    "count": 0,
                    "hasMore": False,
                    "nextCursor": None,
                },
            }
        )

    def read_checkpoints(self, **kwargs):
        self.detail_calls.append(("checkpoints", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        return TaskCockpitCheckpointPageEnvelope.model_validate(
            {
                "tenant": {
                    "orgId": kwargs["org_id"],
                    "projectId": kwargs["project_id"],
                },
                "runId": kwargs["run_id"],
                "evaluatedAt": NOW,
                "membershipCutoff": NOW,
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


def test_run_detail_api_uses_principal_scope_and_has_only_safe_get_surfaces() -> None:
    cockpit = FakeCockpit()
    catalog = FakeCatalog()
    with _client(cockpit, catalog) as client:
        steps = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/steps?limit=20"
        )
        checkpoints = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/checkpoints"
        )
        injected = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/steps?orgId=dev-org"
        )
    assert steps.status_code == 200
    assert checkpoints.status_code == 200
    assert injected.status_code == 400
    assert cockpit.detail_calls == [
        (
            "steps",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
                "limit": 20,
                "cursor": None,
            },
        ),
        (
            "checkpoints",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
                "limit": 50,
                "cursor": None,
            },
        ),
    ]
    assert len(catalog.calls) == 2
