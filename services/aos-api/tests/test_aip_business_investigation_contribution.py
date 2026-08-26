"""BI-W5-07 canonical contribution and handoff composition tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_business_investigation_compiler import (
    BusinessInvestigationCompilation,
)
from aos_api.aip_business_investigation_contribution import (
    BusinessInvestigationContributionBlocked,
    BusinessInvestigationContributionReader,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitSkillContributionEnvelope,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 26, 16, 0, tzinfo=UTC)


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


def runtime(**changes) -> BusinessInvestigationRuntimeBinding:
    value = {
        "tenant": TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        "caseRef": exact("BusinessInvestigationCaseRevision", "case-1", "1"),
        "businessInvestigationRunRef": exact(
            "BusinessInvestigationRun", "investigation-run-1", "2"
        ),
        "compilationHash": "e" * 64,
        "taskRef": {"resourceType": "Task", "resourceId": "task-1", "version": 3},
        "planRef": exact("PlanRevision", "plan-1", "b", revision=2),
        "taskRunRef": {
            "resourceType": "TaskRun",
            "resourceId": "task-run-1",
            "version": 4,
        },
        "taskRunStatus": "paused",
        "planStepCount": 3,
        "bindingHash": "f" * 64,
        "startAuthorized": False,
    }
    value.update(changes)
    return BusinessInvestigationRuntimeBinding.model_validate(value)


def skill_envelope(*, status: str = "available", blockers=None, changes=None):
    item = {
        "contributionId": "agent-run-1:skill-1@1",
        "taskRunRef": {
            "resourceType": "TaskRun",
            "resourceId": "task-run-1",
            "revision": "4",
            "authority": "aip-task-runtime",
        },
        "agentRunRef": {
            "resourceType": "AgentRun",
            "resourceId": "agent-run-1",
            "revision": "2",
            "authority": "aip-agent-runtime",
        },
        "roleRef": exact("AgentTemplate", "data-advisor", "0"),
        "assigneeRef": exact("AgentInstance", "agent-instance-1", "1"),
        "skillRevisionRef": exact("SkillTemplate", "skill-1", "7"),
        "bindingRef": {
            "resourceType": "SkillBinding",
            "resourceId": "binding-1",
            "revision": "4",
            "authority": "aip-capability-registry",
        },
        "logicRevisionRef": exact("LogicRevision", "logic-1", "5"),
        "displayName": "数据参谋 · skill-1",
        "purpose": "只读呈现 AgentRun 的规范贡献。",
        "responsibility": "数据参谋",
        "readiness": {
            "status": status,
            "freshness": "fresh" if status == "available" else "stale",
            "reasonCodes": [] if status == "available" else ["READINESS_EXPIRED"],
            "bindingStatus": "active",
            "lastVerifiedAt": NOW - timedelta(minutes=1),
            "expiresAt": NOW + timedelta(minutes=5),
        },
        "runProjection": {"status": "paused", "updatedAt": NOW},
        "allowedCommands": [],
    }
    item.update(changes or {})
    blocker_codes = list(blockers or [])
    return TaskCockpitSkillContributionEnvelope.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "runId": "task-run-1",
            "taskId": "task-1",
            "evaluatedAt": NOW,
            "projectionStatus": "blocked" if blocker_codes else "ready",
            "blockerCodes": blocker_codes,
            "items": [item],
        }
    )


def empty_skill_envelope() -> TaskCockpitSkillContributionEnvelope:
    return TaskCockpitSkillContributionEnvelope.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "runId": "task-run-1",
            "taskId": "task-1",
            "evaluatedAt": NOW,
            "projectionStatus": "blocked",
            "blockerCodes": ["NO_CANONICAL_AGENT_RUN_CONTRIBUTION"],
            "items": [],
        }
    )


def handoff_envelope(*, with_handoff: bool = False, changes=None):
    handoffs = []
    if with_handoff:
        handoffs = [
            {
                "handoffId": "handoff-1",
                "status": "consumed",
                "version": 2,
                "senderInstanceRef": exact("AgentInstance", "agent-sender", "2"),
                "receiverInstanceRef": exact("AgentInstance", "agent-receiver", "3"),
                "expiresAt": NOW + timedelta(hours=1),
                "consumedAt": NOW - timedelta(minutes=1),
                "createdAt": NOW - timedelta(minutes=2),
                "decisions": [
                    {
                        "decisionId": "decision-1",
                        "revision": 1,
                        "decision": "accepted",
                        "contentHash": "4" * 64,
                        "createdAt": NOW,
                    }
                ],
            }
        ]
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "runId": "task-run-1",
        "taskId": "task-1",
        "evaluatedAt": NOW,
        "responsibilityPlanRef": exact(
            "ResponsibilityPlanRevision", "responsibility-1", "9"
        ),
        "profile": "ecommerce.business-investigation",
        "lifecycle": "frozen",
        "compiledRequiredSlotIds": ["researcher"],
        "slots": [
            {
                "slotId": "researcher",
                "responsibilityType": "research",
                "requiredCapabilityIds": ["ecommerce.research"],
                "returnStage": "portrait",
                "assignee": {
                    "kind": "agent_instance",
                    "resourceId": "agent-instance-1",
                    "version": 1,
                    "operationalReadiness": "unverified",
                    "resolutionReceipts": [],
                },
            }
        ],
        "handoffs": handoffs,
    }
    value.update(changes or {})
    return TaskCockpitResponsibilityHandoffEnvelope.model_validate(value)


class FixedCockpit:
    def __init__(self, skills, handoffs) -> None:
        self.skills = skills
        self.handoffs = handoffs
        self.calls = []

    def read_skill_contributions(self, **kwargs):
        self.calls.append(("skills", kwargs))
        return self.skills

    def read_responsibility_handoffs(self, **kwargs):
        self.calls.append(("handoffs", kwargs))
        return self.handoffs


def test_reader_composes_exact_read_only_contribution_view() -> None:
    cockpit = FixedCockpit(skill_envelope(), handoff_envelope())

    result = BusinessInvestigationContributionReader(cockpit).read(
        SCOPE, compilation(), runtime()
    )

    assert result.projection_status == "ready"
    assert result.blocker_codes == []
    assert result.responsibility_plan_ref == compilation().responsibility_plan_ref
    assert result.skill_contributions.items[0].agent_run_ref.resource_id == "agent-run-1"
    assert result.side_effects.model_dump() == {
        "agent_run_created_count": 0,
        "handoff_created_count": 0,
        "task_run_transition_count": 0,
        "external_business_mutation_count": 0,
    }
    assert cockpit.calls == [
        ("skills", {"org_id": "org-org", "project_id": "dev-project", "run_id": "task-run-1"}),
        ("handoffs", {"org_id": "org-org", "project_id": "dev-project", "run_id": "task-run-1"}),
    ]


def test_reader_preserves_missing_agent_run_as_blocked_without_fabrication() -> None:
    result = BusinessInvestigationContributionReader(
        FixedCockpit(empty_skill_envelope(), handoff_envelope())
    ).read(SCOPE, compilation(), runtime())

    assert result.projection_status == "blocked"
    assert result.blocker_codes == ["NO_CANONICAL_AGENT_RUN_CONTRIBUTION"]
    assert result.skill_contributions.items == []


def test_reader_keeps_stale_contribution_blocked() -> None:
    result = BusinessInvestigationContributionReader(
        FixedCockpit(
            skill_envelope(
                status="stale", blockers=["SKILL_BINDING_READINESS_STALE"]
            ),
            handoff_envelope(),
        )
    ).read(SCOPE, compilation(), runtime())

    assert result.projection_status == "blocked"
    assert result.blocker_codes == [
        "SKILL_BINDING_READINESS_STALE",
        "CONTRIBUTION_NOT_CURRENTLY_AVAILABLE",
    ]


@pytest.mark.parametrize(
    ("compilation_value", "runtime_value", "skills", "handoffs", "code"),
    [
        (
            compilation(),
            runtime(tenant={"orgId": "dev-org", "projectId": "dev-project"}),
            skill_envelope(),
            handoff_envelope(),
            "TENANT_DRIFTED",
        ),
        (
            compilation(),
            runtime(taskRef={"resourceType": "Task", "resourceId": "other", "version": 3}),
            skill_envelope(),
            handoff_envelope(),
            "TASK_DRIFTED",
        ),
        (
            compilation(),
            runtime(),
            skill_envelope(changes={"skillRevisionRef": exact("SkillTemplate", "other", "7")}),
            handoff_envelope(),
            "SKILL_REF_DRIFTED",
        ),
        (
            compilation(),
            runtime(),
            skill_envelope(changes={"logicRevisionRef": exact("LogicRevision", "other", "5")}),
            handoff_envelope(),
            "LOGIC_REF_DRIFTED",
        ),
        (
            compilation(),
            runtime(),
            skill_envelope(),
            handoff_envelope(
                changes={
                    "responsibilityPlanRef": exact(
                        "ResponsibilityPlanRevision", "other", "9"
                    )
                }
            ),
            "RESPONSIBILITY_PLAN_DRIFTED",
        ),
    ],
)
def test_reader_fails_closed_on_canonical_drift(
    compilation_value, runtime_value, skills, handoffs, code
) -> None:
    with pytest.raises(BusinessInvestigationContributionBlocked) as captured:
        BusinessInvestigationContributionReader(FixedCockpit(skills, handoffs)).read(
            SCOPE, compilation_value, runtime_value
        )
    assert captured.value.code == code


def test_reader_does_not_fabricate_exact_handoff_envelope_hash() -> None:
    result = BusinessInvestigationContributionReader(
        FixedCockpit(skill_envelope(), handoff_envelope(with_handoff=True))
    ).read(SCOPE, compilation(), runtime())

    assert result.projection_status == "blocked"
    assert result.blocker_codes == ["HANDOFF_EXACT_ENVELOPE_HASH_UNAVAILABLE"]
    assert result.responsibility_handoffs.handoffs[0].decisions[0].content_hash == "4" * 64
    assert "contentHash" not in result.responsibility_handoffs.handoffs[0].model_dump(
        mode="json", by_alias=True
    )
