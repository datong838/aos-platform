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
    TaskCockpitActionReceiptEnvelope,
    TaskCockpitApprovalReviewEnvelope,
    TaskCockpitCheckpointPageEnvelope,
    TaskCockpitCoreEnvelope,
    TaskCockpitProductionContextEnvelope,
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitSkillContributionEnvelope,
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
    assert len(first.blockers) == 2
    assert {blocker.code for blocker in first.blockers} == {
        "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED",
        "TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT",
    }
    assert all(blocker.severity.value == "warning" for blocker in first.blockers)
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


def _production_row() -> dict[str, Any]:
    stage = {
        "stageId": "research",
        "title": "事实调研",
        "dependsOn": [],
        "applicability": {"kind": "always", "profiles": []},
        "requiredSlotIds": ["researcher"],
        "inputSchemaRef": {"type": "schema", "id": "input", "version": "1"},
        "outputSchemaRef": {"type": "schema", "id": "output", "version": "1"},
        "gateRefs": [],
        "checkpointPolicy": {},
        "retryPolicy": {},
        "compensationPolicy": {},
        "applicabilityResult": "applicable",
        "evaluatedProfile": "ecommerce.task-cockpit",
    }
    return {
        "task_id": "task-1",
        "run_id": "run-1",
        "plan_revision_id": "plan-1",
        "plan_revision": 2,
        "plan_content_hash": "a" * 64,
        "steps": [{"stepKey": "research", "title": "事实调研", "inputRefs": []}],
        "risk": {
            "productionContract": {
                "compilerVersion": "w2c.v1",
                "stageTemplateRef": {
                    "resourceType": "StageTemplateRevision",
                    "resourceId": "template-1",
                    "revision": 3,
                    "contentHash": "b" * 64,
                },
                "responsibilityPlanRef": {
                    "resourceType": "ResponsibilityPlanRevision",
                    "resourceId": "responsibility-1",
                    "revision": 4,
                    "contentHash": "c" * 64,
                },
                "stageCompilation": [stage],
                "productionStartGateRequired": True,
                "productionStartGateRef": None,
            }
        },
    }


class ProductionConnection:
    def __init__(self, row: dict[str, Any] | None):
        self.row = row
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return self.row


def _production_cockpit(row: dict[str, Any] | None):
    connection = ProductionConnection(row)

    @contextmanager
    def connect():
        yield connection

    return EcommerceWorkshopTaskCockpit(connect_factory=connect, clock=lambda: NOW), connection


def test_production_context_reads_exact_canonical_stage_mapping() -> None:
    cockpit, connection = _production_cockpit(_production_row())
    result = cockpit.read_production_context(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    assert result.plan_ref.resource_id == "plan-1"
    assert result.stage_template_ref.resource_id == "template-1"
    assert result.responsibility_plan_ref.resource_id == "responsibility-1"
    assert result.applicable_stage_ids == ["research"]
    assert result.not_applicable_stage_ids == []
    assert result.stages[0].required_slot_ids == ["researcher"]
    sql = " ".join(call[0] for call in connection.calls).upper()
    assert "REPEATABLE READ READ ONLY" in sql
    assert "SET LOCAL ROLE AOS_RUNTIME" in sql
    assert "INSERT " not in sql and "UPDATE " not in sql and "DELETE " not in sql
    assert connection.calls[-1][1] == ("org-org", "dev-project", "run-1")


@pytest.mark.parametrize("drift", ["missing_contract", "step_mismatch", "wrong_ref"])
def test_production_context_fails_closed_on_canonical_drift(drift: str) -> None:
    row = _production_row()
    if drift == "missing_contract":
        row["risk"] = {}
    elif drift == "step_mismatch":
        row["steps"][0]["stepKey"] = "invented-stage"
    else:
        row["risk"]["productionContract"]["stageTemplateRef"]["resourceType"] = "BundleRevision"
    cockpit, _ = _production_cockpit(row)
    with pytest.raises(ApiError) as captured:
        cockpit.read_production_context(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_PRODUCTION_CONTEXT_DRIFTED"
    assert captured.value.status_code == 409


def test_production_context_missing_run_is_not_empty_context() -> None:
    cockpit, _ = _production_cockpit(None)
    with pytest.raises(ApiError) as captured:
        cockpit.read_production_context(
            org_id="dev-org", project_id="dev-project", run_id="run-missing"
        )
    assert captured.value.code == "TASK_COCKPIT_RUN_NOT_FOUND"


def _skill_contribution_row() -> dict[str, Any]:
    skill = {
        "assetType": "SkillTemplate",
        "assetId": "ecommerce.skill.D01",
        "revision": 1,
        "contentHash": "a" * 64,
    }
    logic = {
        "assetType": "LogicRevision",
        "assetId": "ecommerce.logic.D01",
        "revision": 2,
        "contentHash": "b" * 64,
    }
    return {
        "agent_run_id": "agent-run-1",
        "task_id": "task-1",
        "task_run_id": "run-1",
        "task_run_ref": {
            "resourceType": "TaskRun",
            "resourceId": "run-1",
            "revision": None,
            "authority": "aip-task-runtime",
        },
        "instance_id": "agent-instance-1",
        "instance_version": 3,
        "instance_ref": {
            "assetType": "AgentInstance",
            "assetId": "agent-instance-1",
            "revision": 3,
            "contentHash": "c" * 64,
        },
        "skill_binding_id": "binding-1",
        "skill_ref": skill,
        "logic_ref": logic,
        "input_refs": [
            {
                "resourceType": "EvidenceBundle",
                "resourceId": "evidence-1",
                "revision": "1",
                "authority": "aip-evidence",
            }
        ],
        "run_status": "running",
        "run_version": 2,
        "run_created_at": NOW - timedelta(minutes=10),
        "run_updated_at": NOW - timedelta(minutes=1),
        "skill_id": "ecommerce.skill.D01",
        "skill_revision": 1,
        "binding_status": "active",
        "binding_version": 4,
        "readiness": "available",
        "readiness_reasons": [],
        "last_evaluated_at": NOW - timedelta(minutes=2),
        "readiness_expires_at": NOW + timedelta(minutes=10),
        "skill_content_hash": "a" * 64,
        "canonical_logic_id": "ecommerce.logic.D01",
        "logic_revision_ref": logic,
        "template_id": "ecommerce.data_advisor",
        "template_revision": 1,
        "template_content_hash": "d" * 64,
        "role_display_name": "数据参谋",
        "role_key": "data_advisor",
    }


class SkillContributionConnection:
    def __init__(self, rows: list[dict[str, Any]], attempts: list[dict[str, Any]] | None = None):
        self.rows = rows
        self.attempts = attempts or []
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        if "SELECT 1 FROM aip_task_run" in self.calls[-1][0]:
            return {"present": 1, "task_id": "task-1"}
        raise AssertionError(f"unexpected fetchone query: {self.calls[-1][0]}")

    def fetchall(self):
        if "FROM aip_agent_run_execution_attempt" in self.calls[-1][0]:
            return self.attempts
        if "FROM aip_agent_run agent" in self.calls[-1][0]:
            return self.rows
        raise AssertionError(f"unexpected fetchall query: {self.calls[-1][0]}")


def _skill_contribution_cockpit(
    rows: list[dict[str, Any]], attempts: list[dict[str, Any]] | None = None
):
    connection = SkillContributionConnection(rows, attempts)

    @contextmanager
    def connect():
        yield connection

    return EcommerceWorkshopTaskCockpit(connect_factory=connect, clock=lambda: NOW), connection


def test_skill_contribution_projects_exact_canonical_agent_run_and_readiness() -> None:
    cockpit, connection = _skill_contribution_cockpit(
        [_skill_contribution_row()],
        attempts=[
            {
                "agent_run_id": "agent-run-1",
                "output_artifact_ref": {
                    "resourceType": "Artifact",
                    "resourceId": "artifact-1",
                    "revision": "1",
                    "authority": "aip-artifact",
                },
            }
        ],
    )

    result = cockpit.read_skill_contributions(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )

    assert result.projection_status == "ready"
    assert result.blocker_codes == []
    assert len(result.items) == 1
    contribution = result.items[0]
    assert contribution.skill_revision_ref.resource_id == "ecommerce.skill.D01"
    assert contribution.logic_revision_ref.resource_id == "ecommerce.logic.D01"
    assert contribution.role_ref.resource_id == "ecommerce.data_advisor"
    assert contribution.readiness.status == "available"
    assert contribution.readiness.freshness == "fresh"
    assert contribution.allowed_commands == []
    assert contribution.output_artifact_refs[0].resource_id == "artifact-1"
    sql = " ".join(call[0] for call in connection.calls).upper()
    assert "REPEATABLE READ READ ONLY" in sql
    assert "SET LOCAL ROLE AOS_RUNTIME" in sql
    assert not any(token in sql for token in ("INSERT ", "UPDATE ", "DELETE "))


def test_skill_contribution_empty_and_stale_states_fail_closed_without_fabrication() -> None:
    empty, _ = _skill_contribution_cockpit([])
    empty_result = empty.read_skill_contributions(
        org_id="dev-org", project_id="dev-project", run_id="run-1"
    )
    assert empty_result.projection_status == "blocked"
    assert empty_result.blocker_codes == ["NO_CANONICAL_AGENT_RUN_CONTRIBUTION"]
    assert empty_result.items == []

    row = _skill_contribution_row()
    row["readiness_expires_at"] = NOW - timedelta(seconds=1)
    stale, _ = _skill_contribution_cockpit([row])
    stale_result = stale.read_skill_contributions(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    assert stale_result.items[0].readiness.status == "stale"
    assert "SKILL_BINDING_READINESS_STALE" in stale_result.items[0].readiness.reason_codes


def test_skill_contribution_rejects_exact_skill_drift() -> None:
    row = _skill_contribution_row()
    row["skill_content_hash"] = "e" * 64
    cockpit, _ = _skill_contribution_cockpit([row])
    with pytest.raises(ApiError) as captured:
        cockpit.read_skill_contributions(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_SKILL_CONTRIBUTION_DRIFTED"
    assert captured.value.status_code == 409


def _responsibility_row() -> dict[str, Any]:
    return {
        "plan_id": "responsibility-1",
        "revision": 4,
        "profile": "ecommerce.task-cockpit",
        "slots": [
            {
                "slotId": "researcher",
                "responsibilityType": "research",
                "requiredCapabilityIds": ["ecommerce.research"],
                "inputSchemaRef": {"resourceType": "Schema", "resourceId": "input-1", "revision": "1", "authority": "postgresql"},
                "outputSchemaRef": {"resourceType": "Schema", "resourceId": "output-1", "revision": "1", "authority": "postgresql"},
                "gateRefs": [],
                "returnStage": "research",
                "assignee": {"kind": "agent_instance", "resourceId": "agent-research", "version": 2},
            }
        ],
        "content_hash": "c" * 64,
        "lifecycle": "frozen",
    }


def _asset_ref(identifier: str) -> dict[str, Any]:
    return {"assetType": "AgentInstance", "assetId": identifier, "revision": 2, "contentHash": "d" * 64}


class ResponsibilityConnection:
    def __init__(self, *, responsibility: dict[str, Any] | None = None, resolutions: list[dict[str, Any]] | None = None):
        self.responsibility = _responsibility_row() if responsibility is None else responsibility
        self.resolutions = [] if resolutions is None else resolutions
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        sql = self.calls[-1][0]
        if "FROM aip_task_run run" in sql:
            return _production_row()
        if "FROM aip_responsibility_plan_revision" in sql:
            return self.responsibility
        raise AssertionError(f"unexpected fetchone query: {sql}")

    def fetchall(self):
        sql = self.calls[-1][0]
        if "FROM aip_assignee_resolution_receipt" in sql:
            return self.resolutions
        if "FROM aip_handoff_envelope" in sql:
            return [{
                "handoff_id": "handoff-1",
                "task_ref": {"resourceType": "Task", "resourceId": "task-1", "revision": "1", "authority": "postgresql"},
                "task_run_ref": {"resourceType": "TaskRun", "resourceId": "run-1", "revision": "1", "authority": "postgresql"},
                "sender_instance_ref": _asset_ref("agent-sender"),
                "receiver_instance_ref": _asset_ref("agent-receiver"),
                "status": "consumed",
                "version": 2,
                "expires_at": NOW + timedelta(hours=1),
                "consumed_at": NOW - timedelta(minutes=1),
                "created_at": NOW - timedelta(minutes=2),
            }]
        if "FROM aip_handoff_decision_revision decision" in sql:
            return [{
                "decision_id": "decision-1",
                "handoff_id": "handoff-1",
                "revision": 1,
                "decision": "accepted",
                "reason_code": None,
                "gap_codes": [],
                "content_hash": "e" * 64,
                "created_at": NOW,
            }]
        raise AssertionError(f"unexpected fetchall query: {sql}")


def _responsibility_cockpit(*, responsibility: dict[str, Any] | None = None, resolutions: list[dict[str, Any]] | None = None):
    connection = ResponsibilityConnection(responsibility=responsibility, resolutions=resolutions)

    @contextmanager
    def connect():
        yield connection

    return EcommerceWorkshopTaskCockpit(connect_factory=connect, clock=lambda: NOW), connection


def test_responsibility_handoffs_read_exact_minimal_canonical_timeline() -> None:
    cockpit, connection = _responsibility_cockpit()
    result = cockpit.read_responsibility_handoffs(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    assert result.responsibility_plan_ref.resource_id == "responsibility-1"
    assert result.compilation_readiness == "ready_at_compile"
    assert result.compiled_required_slot_ids == ["researcher"]
    assert result.slots[0].assignee.operational_readiness == "unverified"
    assert result.handoffs[0].decisions[0].decision == "accepted"
    payload = result.model_dump(mode="json", by_alias=True)
    assert "bearerToken" not in str(payload)
    assert "context" not in str(payload)
    sql = " ".join(call[0] for call in connection.calls).upper()
    assert "REPEATABLE READ READ ONLY" in sql
    assert "SET LOCAL ROLE AOS_RUNTIME" in sql
    assert "INSERT " not in sql and "UPDATE " not in sql and "DELETE " not in sql


def _resolution_row(*, status: str = "resolved", created_at: datetime = NOW) -> dict[str, Any]:
    return {
        "receipt_id": f"receipt-{status}",
        "subject_id": "responsibility-plan:responsibility-1@4/slot:researcher",
        "kind": "agent_instance",
        "resource_id": "agent-research",
        "version": 2,
        "status": status,
        "blocker_codes": [] if status == "resolved" else ["AGENT_INSTANCE_MISSING"],
        "content_hash": "9" * 64,
        "created_at": created_at,
        "actor": "must-not-leak",
        "resolved_ref": "must-not-leak",
    }


def test_responsibility_handoffs_exposes_exact_resolution_observation_without_private_fields() -> None:
    cockpit, _ = _responsibility_cockpit(resolutions=[_resolution_row()])
    result = cockpit.read_responsibility_handoffs(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    assignee = result.slots[0].assignee
    assert assignee.operational_readiness == "resolved_at_observation"
    assert assignee.resolution_receipts[0].status == "resolved"
    payload = result.model_dump(mode="json", by_alias=True)
    assert "must-not-leak" not in str(payload)
    assert "actor" not in str(payload)
    assert "resolvedRef" not in str(payload)


def test_responsibility_handoffs_fails_closed_on_resolution_assignee_drift() -> None:
    receipt = _resolution_row()
    receipt["resource_id"] = "agent-other"
    cockpit, _ = _responsibility_cockpit(resolutions=[receipt])
    with pytest.raises(ApiError) as captured:
        cockpit.read_responsibility_handoffs(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_DRIFTED"


def test_responsibility_handoffs_fails_closed_on_same_time_resolution_conflict() -> None:
    blocked = _resolution_row(status="blocked")
    blocked["receipt_id"] = "receipt-blocked"
    resolved = _resolution_row(status="resolved")
    resolved["receipt_id"] = "receipt-resolved"
    cockpit, _ = _responsibility_cockpit(resolutions=[blocked, resolved])
    with pytest.raises(ApiError) as captured:
        cockpit.read_responsibility_handoffs(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_DRIFTED"


def test_responsibility_handoffs_fail_closed_on_exact_hash_drift() -> None:
    row = _responsibility_row()
    row["content_hash"] = "f" * 64
    cockpit, _ = _responsibility_cockpit(responsibility=row)
    with pytest.raises(ApiError) as captured:
        cockpit.read_responsibility_handoffs(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_RESPONSIBILITY_HANDOFF_DRIFTED"
    assert captured.value.status_code == 409


def test_responsibility_handoff_contract_rejects_uncovered_compiled_slot() -> None:
    cockpit, _ = _responsibility_cockpit()
    result = cockpit.read_responsibility_handoffs(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    payload = result.model_dump(mode="json", by_alias=True)
    payload["compiledRequiredSlotIds"] = ["missing"]
    with pytest.raises(ValidationError):
        TaskCockpitResponsibilityHandoffEnvelope.model_validate(payload)


class ApprovalReviewConnection:
    def __init__(self, *, drift_return: bool = False):
        self.drift_return = drift_return
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        sql = self.calls[-1][0]
        if "FROM aip_task_run run" in sql:
            return {
                "run_id": "run-1", "task_id": "task-1",
                "plan_revision_id": "plan-1", "plan_revision": 2,
                "plan_content_hash": "a" * 64, "approval_status": "approved",
                "approved_by": "checker-1", "approved_at": NOW - timedelta(hours=1),
            }
        raise AssertionError(f"unexpected fetchone query: {sql}")

    def fetchall(self):
        sql = self.calls[-1][0]
        if "FROM aip_action_proposal" in sql and "approval" not in sql.lower():
            return [{
                "proposal_id": "proposal-1", "action_type_id": "ecommerce.review",
                "status": "approved", "expires_at": NOW + timedelta(hours=1),
                "version": 2, "proposal_hash": "b" * 64,
                "created_at": NOW - timedelta(minutes=20),
            }]
        if "FROM aip_action_approval_event approval" in sql:
            return [{
                "approval_event_id": "approval-1", "proposal_id": "proposal-1",
                "proposal_version": 2, "proposal_hash": "b" * 64,
                "decision": "approved", "actor_id": "checker-2",
                "expires_at": NOW + timedelta(minutes=30),
                "created_at": NOW - timedelta(minutes=10),
            }]
        if "FROM aip_review_issue issue" in sql and "SELECT issue.issue_id" in sql:
            return [
                {
                    "issue_id": "issue-open", "rule_ref": {
                        "resourceType": "EvalRuleRevision", "resourceId": "rule-1",
                        "revision": 1, "contentHash": "c" * 64,
                    }, "severity": "warning", "artifact_id": "artifact-1",
                    "artifact_hash": "d" * 64, "canonical_artifact_hash": "d" * 64,
                    "eval_report_id": "report-1", "eval_report_revision": 1,
                    "eval_report_hash": "e" * 64, "evidence_refs": [],
                    "return_stage": "research", "status": "open", "version": 1,
                    "created_at": NOW - timedelta(minutes=8),
                },
                {
                    "issue_id": "issue-returned", "rule_ref": {
                        "resourceType": "EvalRuleRevision", "resourceId": "rule-2",
                        "revision": 1, "contentHash": "f" * 64,
                    }, "severity": "error", "artifact_id": "artifact-2",
                    "artifact_hash": "1" * 64, "canonical_artifact_hash": "1" * 64,
                    "eval_report_id": "report-2", "eval_report_revision": 2,
                    "eval_report_hash": "2" * 64,
                    "evidence_refs": [{"resourceType": "Evidence", "resourceId": "e-1"}],
                    "return_stage": "review", "status": "returned", "version": 2,
                    "created_at": NOW - timedelta(minutes=6),
                },
            ]
        if "FROM aip_review_issue_event event" in sql:
            return [
                {"event_id": "event-open", "issue_id": "issue-open", "sequence": 1,
                 "event_type": "opened", "issue_version": 1, "payload_hash": "3" * 64,
                 "actor": "eval-service", "created_at": NOW - timedelta(minutes=8)},
                {"event_id": "event-return-open", "issue_id": "issue-returned", "sequence": 1,
                 "event_type": "opened", "issue_version": 1, "payload_hash": "4" * 64,
                 "actor": "eval-service", "created_at": NOW - timedelta(minutes=6)},
                {"event_id": "event-returned", "issue_id": "issue-returned", "sequence": 2,
                 "event_type": "returned", "issue_version": 2, "payload_hash": "5" * 64,
                 "actor": "reviewer", "created_at": NOW - timedelta(minutes=4)},
            ]
        if "FROM aip_return_decision decision" in sql:
            return [{
                "decision_id": "return-1", "issue_id": "issue-returned",
                "issue_version": 1, "run_id": "run-1", "step_key": "review",
                "step_run_id": "step-run-2", "attempt": 2,
                "decision_hash": "6" * 64, "created_at": NOW - timedelta(minutes=4),
                "step_run_run_id": "run-other" if self.drift_return else "run-1",
                "step_run_step_key": "review", "step_run_attempt": 2,
            }]
        raise AssertionError(f"unexpected fetchall query: {sql}")


def _approval_review_cockpit(*, drift_return: bool = False):
    connection = ApprovalReviewConnection(drift_return=drift_return)

    @contextmanager
    def connect():
        yield connection

    return EcommerceWorkshopTaskCockpit(connect_factory=connect, clock=lambda: NOW), connection


def test_approval_review_reads_exact_facts_and_preserves_unresolved_attempt() -> None:
    cockpit, connection = _approval_review_cockpit()
    result = cockpit.read_approval_review_issues(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    assert result.plan_approval.approval_status == "approved"
    assert result.plan_approval.navigation.command_readiness == "read_only_fact"
    assert result.action_approvals[0].decisions[0].decision == "approved"
    assert result.action_approvals[0].navigation.command_readiness == "destination_reauthorization_required"
    assert result.review_issue_count == 2
    assert result.unresolved_attempt_count == 1
    assert result.review_issues[0].lineage_readiness == "attempt_unresolved"
    assert result.review_issues[1].return_lineage is not None
    assert result.review_issues[1].return_lineage.attempt == 2
    assert len(result.plan_approval.navigation.return_focus_token) == 64
    sql = " ".join(call[0] for call in connection.calls).upper()
    assert "REPEATABLE READ READ ONLY" in sql
    assert "SET LOCAL ROLE AOS_RUNTIME" in sql
    assert "INSERT " not in sql and "UPDATE " not in sql and "DELETE " not in sql


def test_approval_review_fails_closed_on_return_step_run_drift() -> None:
    cockpit, _ = _approval_review_cockpit(drift_return=True)
    with pytest.raises(ApiError) as captured:
        cockpit.read_approval_review_issues(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_APPROVAL_REVIEW_DRIFTED"


def test_approval_review_contract_rejects_count_drift() -> None:
    cockpit, _ = _approval_review_cockpit()
    payload = cockpit.read_approval_review_issues(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    ).model_dump(mode="json", by_alias=True)
    payload["reviewIssueCount"] = 1
    with pytest.raises(ValidationError):
        TaskCockpitApprovalReviewEnvelope.model_validate(payload)


class ActionReceiptConnection:
    def __init__(self, *, drift_fingerprint: bool = False):
        self.drift_fingerprint = drift_fingerprint
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        sql = self.calls[-1][0]
        if "SELECT run_id,task_id FROM aip_task_run" in sql:
            return {"run_id": "run-1", "task_id": "task-1"}
        raise AssertionError(f"unexpected fetchone query: {sql}")

    def fetchall(self):
        sql = self.calls[-1][0]
        if "FROM aip_action_proposal" in sql and "SELECT proposal_id" in sql:
            return [
                {"proposal_id": "proposal-unknown", "task_id": "task-1", "run_id": "run-1", "action_type_id": "ecommerce.notify", "status": "unknown", "version": 4, "proposal_hash": "a" * 64, "created_at": NOW - timedelta(minutes=10)},
                {"proposal_id": "proposal-resolved", "task_id": "task-1", "run_id": "run-1", "action_type_id": "ecommerce.refund", "status": "reconciled", "version": 5, "proposal_hash": "b" * 64, "created_at": NOW - timedelta(minutes=8)},
            ]
        if "FROM aip_action_execution_lease lease" in sql:
            return [
                {"lease_id": "lease-unknown", "proposal_id": "proposal-unknown", "proposal_hash": "a" * 64, "attempt": 1, "created_at": NOW - timedelta(minutes=9)},
                {"lease_id": "lease-resolved", "proposal_id": "proposal-resolved", "proposal_hash": "b" * 64, "attempt": 1, "created_at": NOW - timedelta(minutes=7)},
            ]
        if "FROM aip_action_receipt receipt" in sql:
            return [
                {"receipt_id": "receipt-unknown", "proposal_id": "proposal-unknown", "lease_id": "lease-unknown", "status": "unknown", "provider_request_id": None, "request_fingerprint": "c" * 64, "evidence_refs": [], "payload": {}, "receipt_kind": "initial", "supersedes_receipt_id": None, "created_at": NOW - timedelta(minutes=8)},
                {"receipt_id": "receipt-original", "proposal_id": "proposal-resolved", "lease_id": "lease-resolved", "status": "unknown", "provider_request_id": "provider-secret", "request_fingerprint": "d" * 64, "evidence_refs": [{"resourceType": "Evidence", "resourceId": "e-1"}], "payload": {}, "receipt_kind": "initial", "supersedes_receipt_id": None, "created_at": NOW - timedelta(minutes=6)},
                {"receipt_id": "receipt-reconcile", "proposal_id": "proposal-resolved", "lease_id": "lease-resolved", "status": "reconciled", "provider_request_id": "provider-secret", "request_fingerprint": ("e" if self.drift_fingerprint else "d") * 64, "evidence_refs": [], "payload": {"resolvedStatus": "applied", "provider": {"secret": "not-exposed"}}, "receipt_kind": "reconcile", "supersedes_receipt_id": "receipt-original", "created_at": NOW - timedelta(minutes=4)},
            ]
        raise AssertionError(f"unexpected fetchall query: {sql}")


def _action_receipt_cockpit(*, drift_fingerprint: bool = False):
    connection = ActionReceiptConnection(drift_fingerprint=drift_fingerprint)

    @contextmanager
    def connect():
        yield connection

    return EcommerceWorkshopTaskCockpit(connect_factory=connect, clock=lambda: NOW), connection


def test_action_receipts_preserve_unknown_and_exact_reconcile_chain() -> None:
    cockpit, connection = _action_receipt_cockpit()
    result = cockpit.read_action_receipts(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    )
    assert result.proposal_count == 2
    assert result.receipt_count == 3
    assert result.unknown_receipt_count == 2
    assert result.reconcile_required_count == 1
    assert result.reconciled_receipt_count == 1
    assert [item.reconciliation_state for item in result.executions] == ["required", "resolved"]
    assert result.executions[1].receipts[1].resolved_status == "applied"
    serialized = result.model_dump_json(by_alias=True)
    assert "provider-secret" not in serialized
    assert '"secret"' not in serialized
    sql = " ".join(call[0] for call in connection.calls).upper()
    assert "REPEATABLE READ READ ONLY" in sql
    assert "SET LOCAL ROLE AOS_RUNTIME" in sql
    assert "INSERT " not in sql and "UPDATE " not in sql and "DELETE " not in sql


def test_action_receipts_fail_closed_on_reconcile_fingerprint_drift() -> None:
    cockpit, _ = _action_receipt_cockpit(drift_fingerprint=True)
    with pytest.raises(ApiError) as captured:
        cockpit.read_action_receipts(
            org_id="org-org", project_id="dev-project", run_id="run-1"
        )
    assert captured.value.code == "TASK_COCKPIT_ACTION_RECEIPT_DRIFTED"


def test_action_receipt_contract_rejects_count_drift() -> None:
    cockpit, _ = _action_receipt_cockpit()
    payload = cockpit.read_action_receipts(
        org_id="org-org", project_id="dev-project", run_id="run-1"
    ).model_dump(mode="json", by_alias=True)
    payload["reconcileRequiredCount"] = 0
    with pytest.raises(ValidationError):
        TaskCockpitActionReceiptEnvelope.model_validate(payload)


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

    def read_production_context(self, **kwargs):
        self.detail_calls.append(("production-context", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        row = _production_row()
        return TaskCockpitProductionContextEnvelope.model_validate(
            {
                "tenant": {"orgId": kwargs["org_id"], "projectId": kwargs["project_id"]},
                "runId": kwargs["run_id"],
                "taskId": row["task_id"],
                "evaluatedAt": NOW,
                "planRef": {
                    "resourceType": "PlanRevision",
                    "resourceId": row["plan_revision_id"],
                    "revision": row["plan_revision"],
                    "contentHash": row["plan_content_hash"],
                },
                "stageTemplateRef": row["risk"]["productionContract"]["stageTemplateRef"],
                "responsibilityPlanRef": row["risk"]["productionContract"]["responsibilityPlanRef"],
                "compilerVersion": "w2c.v1",
                "stages": [{
                    "stageId": "research",
                    "title": "事实调研",
                    "dependsOn": [],
                    "requiredSlotIds": ["researcher"],
                    "applicabilityResult": "applicable",
                    "evaluatedProfile": "ecommerce.task-cockpit",
                }],
                "applicableStageIds": ["research"],
                "notApplicableStageIds": [],
            }
        )

    def read_skill_contributions(self, **kwargs):
        self.detail_calls.append(("skill-contributions", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        return TaskCockpitSkillContributionEnvelope.model_validate(
            {
                "tenant": {"orgId": kwargs["org_id"], "projectId": kwargs["project_id"]},
                "runId": kwargs["run_id"],
                "taskId": "task-1",
                "evaluatedAt": NOW,
                "projectionStatus": "blocked",
                "blockerCodes": ["NO_CANONICAL_AGENT_RUN_CONTRIBUTION"],
                "items": [],
            }
        )

    def read_responsibility_handoffs(self, **kwargs):
        self.detail_calls.append(("responsibility-handoffs", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        cockpit, _ = _responsibility_cockpit()
        return cockpit.read_responsibility_handoffs(**kwargs)

    def read_approval_review_issues(self, **kwargs):
        self.detail_calls.append(("approval-review-issues", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        cockpit, _ = _approval_review_cockpit()
        return cockpit.read_approval_review_issues(**kwargs)

    def read_action_receipts(self, **kwargs):
        self.detail_calls.append(("action-receipts", kwargs))
        if self.fail:
            raise TaskCockpitPersistenceError("sensitive database detail")
        cockpit, _ = _action_receipt_cockpit()
        return cockpit.read_action_receipts(**kwargs)


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
        production = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/production-context"
        )
        contributions = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/skill-contributions"
        )
        responsibility = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/responsibility-handoffs"
        )
        approval_review = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/approval-review-issues"
        )
        action_receipts = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/action-receipts"
        )
        injected = client.get(
            "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/steps?orgId=dev-org"
        )
    assert steps.status_code == 200
    assert checkpoints.status_code == 200
    assert production.status_code == 200
    assert contributions.status_code == 200
    assert responsibility.status_code == 200
    assert approval_review.status_code == 200
    assert action_receipts.status_code == 200
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
        (
            "production-context",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
            },
        ),
        (
            "skill-contributions",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
            },
        ),
        (
            "responsibility-handoffs",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
            },
        ),
        (
            "approval-review-issues",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
            },
        ),
        (
            "action-receipts",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "run_id": "run-1",
            },
        ),
    ]
    assert len(catalog.calls) == 7
