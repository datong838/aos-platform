"""BI-W5-02 canonical Task runtime reuse tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_business_investigation_compiler import (
    BusinessInvestigationCompilation,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinder,
    BusinessInvestigationRuntimeBlocked,
)
from aos_api.aip_contracts import ActorRef, PlanStep, TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_task_models import (
    PlanRevisionSnapshot,
    TaskRunSnapshot,
    TaskSnapshot,
    TaskTimeline,
)
from aos_api.public_contracts import TaskStatus
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def exact(kind: str, identity: str, fill: str, revision: int = 1) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=revision,
        content_hash=fill * 64,
    )


def compilation(**changes) -> BusinessInvestigationCompilation:
    value = {
        "tenant": TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        "taskId": "task-1",
        "caseRef": exact("BusinessInvestigationCaseRevision", "case-1", "1"),
        "runRef": exact("BusinessInvestigationRun", "investigation-run-1", "2"),
        "taskBriefRef": exact("TaskBriefRevision", "brief-1", "3"),
        "profileRef": exact("InvestigationProfileRevision", "profile-1", "4"),
        "logicRef": exact("LogicRevision", "logic-1", "5"),
        "stageTemplateRef": exact("StageTemplateRevision", "stage-1", "6"),
        "orderedSkillRefs": [exact("SkillTemplateRevision", "skill-1", "7")],
        "skillBindingSetRef": exact("SkillBindingSetRevision", "binding-1", "8"),
        "responsibilityPlanRef": exact(
            "ResponsibilityPlanRevision", "responsibility-1", "9"
        ),
        "productionContextRef": exact("ProductionContextRevision", "context-1", "a"),
        "planRef": exact("PlanRevision", "plan-1", "b", revision=2),
        "normalizedStageIds": ["portrait", "diagnosis", "solution-design"],
        "stageCompilationHash": "c" * 64,
        "inputHash": "d" * 64,
        "compilationHash": "e" * 64,
        "runtimeAuthorized": False,
        "createdAt": NOW,
    }
    value.update(changes)
    return BusinessInvestigationCompilation.model_validate(value)


def timeline(*, checkpoints=None, run_changes=None, plan_changes=None, task_changes=None):
    actor = ActorRef(actor_type="human", actor_id="owner")
    task_value = {
        "id": "task-1",
        "type": "business-investigation",
        "title": "investigation",
        "status": TaskStatus.APPROVED,
        "priority": 50,
        "createdBy": actor,
        "createdAt": NOW,
        "currentPlanRevisionId": "plan-1",
        "version": 3,
        "updatedAt": NOW,
    }
    task_value.update(task_changes or {})
    plan_value = {
        "id": "plan-1",
        "taskId": "task-1",
        "revision": 2,
        "contentHash": "b" * 64,
        "steps": [PlanStep(stepKey="portrait", title="portrait")],
        "approvalStatus": "approved",
        "createdBy": actor,
        "createdAt": NOW,
    }
    plan_value.update(plan_changes or {})
    run_value = {
        "id": "task-run-1",
        "taskId": "task-1",
        "planRevisionId": "plan-1",
        "status": TaskRunStatus.PAUSED,
        "lastCheckpointId": "checkpoint-2",
        "version": 4,
        "createdBy": actor,
        "createdAt": NOW,
        "updatedAt": NOW,
    }
    run_value.update(run_changes or {})
    if checkpoints is None:
        checkpoints = [
            {
                "checkpoint_id": "checkpoint-1",
                "run_id": "task-run-1",
                "plan_revision_id": "plan-1",
                "sequence": 1,
                "state_hash": "1" * 64,
            },
            {
                "checkpoint_id": "checkpoint-2",
                "run_id": "task-run-1",
                "plan_revision_id": "plan-1",
                "sequence": 2,
                "state_hash": "2" * 64,
            },
        ]
    return TaskTimeline(
        task=TaskSnapshot.model_validate(task_value),
        plan=PlanRevisionSnapshot.model_validate(plan_value),
        run=TaskRunSnapshot.model_validate(run_value),
        checkpoints=checkpoints,
    )


class FixedReader:
    def __init__(self, value: TaskTimeline | Exception) -> None:
        self.value = value
        self.calls = []

    def timeline(self, scope, run_id):
        self.calls.append((scope, run_id))
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def test_binder_reuses_exact_canonical_runtime_and_is_deterministic() -> None:
    reader = FixedReader(timeline())
    binder = BusinessInvestigationRuntimeBinder(reader)
    first = binder.bind(SCOPE, compilation(), "task-run-1")
    second = binder.bind(SCOPE, compilation(), "task-run-1")

    assert first.binding_hash == second.binding_hash
    assert first.task_ref.resource_type == "Task"
    assert first.plan_ref == compilation().plan_ref
    assert first.task_run_ref.resource_type == "TaskRun"
    assert first.checkpoint_ref is not None
    assert first.checkpoint_ref.resource_id == "checkpoint-2"
    assert first.start_authorized is False
    assert reader.calls == [(SCOPE, "task-run-1"), (SCOPE, "task-run-1")]


def test_binder_allows_canonical_run_before_first_checkpoint() -> None:
    value = timeline(
        checkpoints=[],
        run_changes={"status": "queued", "lastCheckpointId": None},
    )
    result = BusinessInvestigationRuntimeBinder(FixedReader(value)).bind(
        SCOPE, compilation(), "task-run-1"
    )
    assert result.checkpoint_ref is None
    assert result.task_run_status is TaskRunStatus.QUEUED


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (timeline(plan_changes={"approvalStatus": "draft"}), "PLAN_NOT_APPROVED"),
        (timeline(plan_changes={"contentHash": "f" * 64}), "PLAN_REF_DRIFTED"),
        (timeline(run_changes={"planRevisionId": "plan-other"}), "TASK_RUN_PLAN_DRIFTED"),
        (
            timeline(
                checkpoints=[
                    {
                        "checkpoint_id": "checkpoint-2",
                        "run_id": "task-run-1",
                        "plan_revision_id": "plan-1",
                        "sequence": 2,
                        "state_hash": "2" * 64,
                    },
                    {
                        "checkpoint_id": "checkpoint-1",
                        "run_id": "task-run-1",
                        "plan_revision_id": "plan-1",
                        "sequence": 1,
                        "state_hash": "1" * 64,
                    },
                ]
            ),
            "CHECKPOINT_SEQUENCE_DRIFTED",
        ),
        (
            timeline(
                checkpoints=[
                    {
                        "checkpoint_id": "checkpoint-2",
                        "run_id": "other-run",
                        "plan_revision_id": "plan-1",
                        "sequence": 2,
                        "state_hash": "2" * 64,
                    }
                ]
            ),
            "CHECKPOINT_RUN_DRIFTED",
        ),
    ],
)
def test_runtime_or_lineage_drift_fails_closed(value, code) -> None:
    with pytest.raises(BusinessInvestigationRuntimeBlocked, match=code):
        BusinessInvestigationRuntimeBinder(FixedReader(value)).bind(
            SCOPE, compilation(), "task-run-1"
        )


def test_cross_tenant_or_unresolved_timeline_fails_closed() -> None:
    reader = FixedReader(RuntimeError("not found"))
    with pytest.raises(
        BusinessInvestigationRuntimeBlocked, match="TIMELINE_RESOLUTION_FAILED"
    ):
        BusinessInvestigationRuntimeBinder(reader).bind(
            SCOPE, compilation(), "task-run-1"
        )
    assert reader.calls == [(SCOPE, "task-run-1")]

    with pytest.raises(
        BusinessInvestigationRuntimeBlocked, match="COMPILATION_TENANT_MISMATCH"
    ):
        BusinessInvestigationRuntimeBinder(FixedReader(timeline())).bind(
            OTHER_SCOPE, compilation(), "task-run-1"
        )


def test_latest_checkpoint_must_match_task_run_authority() -> None:
    with pytest.raises(
        BusinessInvestigationRuntimeBlocked, match="LATEST_CHECKPOINT_DRIFTED"
    ):
        BusinessInvestigationRuntimeBinder(
            FixedReader(timeline(run_changes={"lastCheckpointId": "checkpoint-1"}))
        ).bind(SCOPE, compilation(), "task-run-1")
