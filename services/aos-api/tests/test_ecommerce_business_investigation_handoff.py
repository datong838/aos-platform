from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanRevision,
)
from aos_api.ecommerce_business_investigation_handoff import (
    BusinessInvestigationHandoffBlocked,
    CompileBusinessInvestigationHandoffRequest,
    EcommerceBusinessInvestigationHandoffService,
)
from aos_api.tenant_scope import TenantScope
from test_ecommerce_workshop_handoff import _compiler


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 27, 13, tzinfo=UTC)
HASH = "a" * 64


def exact(kind: str, identity: str, *, prefixed: bool = True):
    return InvestigationExactRef(
        resourceType=kind,
        resourceId=identity,
        revision=1,
        contentHash=("sha256:" if prefixed else "") + HASH,
    )


def plan_ref() -> AnalystExactRef:
    return AnalystExactRef(
        resourceType="GrowthPlanRevision",
        resourceId="growth-plan-1",
        revision=2,
        contentHash=HASH,
    )


def approved_plan() -> GrowthPlanRevision:
    return GrowthPlanRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "planId": "growth-plan-1",
            "revision": 2,
            "version": 2,
            "priorRef": {
                "resourceType": "GrowthPlanRevision",
                "resourceId": "growth-plan-1",
                "revision": 1,
                "contentHash": "b" * 64,
            },
            "lifecycle": "approved",
            "decisionRef": {
                "resourceType": "DecisionSummaryRevision",
                "resourceId": "decision-1",
                "revision": 1,
                "contentHash": "c" * 64,
            },
            "objective": "增长",
            "constraints": [],
            "budget": "0",
            "expectedEffect": "受控验证",
            "confidence": 0.7,
            "stopConditions": ["证据过期"],
            "items": [
                {
                    "itemId": "item-1",
                    "taskType": "analysis",
                    "title": "复核",
                    "objective": "复核增长假设",
                }
            ],
            "approvedAt": NOW,
            "contentHash": HASH,
            "createdBy": "reviewer",
            "createdAt": NOW,
        }
    )


def compile_receipt() -> BusinessInvestigationCompilationReceipt:
    def production_exact(kind: str, identity: str, fill: str):
        return ExactRevisionRef(
            resourceType=kind,
            resourceId=identity,
            revision=1,
            contentHash=fill * 64,
        )

    return BusinessInvestigationCompilationReceipt(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"),
        receiptId="compile-receipt-1",
        commandId="compile-command-1",
        requestHash="sha256:" + "1" * 64,
        runRef=exact("BusinessInvestigationRun", "run-1"),
        taskId="task-1",
        planRef=production_exact("PlanRevision", "plan-1", "2"),
        profileRef=production_exact("InvestigationProfileRevision", "profile-1", "3"),
        logicRef=production_exact("LogicRevision", "logic-1", "4"),
        skillBindingSetRef=production_exact("SkillBindingSetRevision", "skills-1", "5"),
        responsibilityPlanRef=production_exact(
            "ResponsibilityPlanRevision", "roles-1", "6"
        ),
        inputHash="7" * 64,
        stageCompilationHash="8" * 64,
        compilationHash="9" * 64,
        createdAt=NOW,
    )


class Projection:
    def __init__(self, *, artifact_count=4):
        self.artifact_count = artifact_count

    def build(self, scope, run_id, *, observed_at):
        assert scope == SCOPE and run_id == "run-1" and observed_at == NOW
        refs = [
            exact(kind, f"artifact-{index}")
            for index, kind in enumerate(
                (
                    "BusinessDossierRevision",
                    "ProblemMapRevision",
                    "OpportunityMapRevision",
                    "SolutionPortfolioRevision",
                )[: self.artifact_count]
            )
        ]
        return SimpleNamespace(
            run_ref=exact("BusinessInvestigationRun", "run-1"),
            runtime=SimpleNamespace(
                binding_status="bound",
                task_id="task-1",
                task_run_ref=SimpleNamespace(resource_id="run-1", version=7),
            ),
            artifacts=[SimpleNamespace(status="bound", artifact_ref=item) for item in refs]
            + [SimpleNamespace(status="missing", artifact_ref=None)] * (4 - len(refs)),
        )


class Receipts:
    def get_for_run(self, scope, run_ref):
        assert scope == SCOPE and run_ref.resource_id == "run-1"
        return compile_receipt()


class Plans:
    def __init__(self, *, current=True, item=None):
        self.current = current
        self.item = item or approved_plan()

    def get_plan_exact(self, scope, ref):
        assert scope == SCOPE and ref == plan_ref()
        return self.item

    def is_current_plan(self, scope, ref):
        return scope == SCOPE and ref == plan_ref() and self.current


class Tasks:
    def get_task(self, scope, task_id):
        assert scope == SCOPE and task_id == "task-1"
        return SimpleNamespace(id="task-1", version=4)

    def get_run(self, scope, run_id):
        assert scope == SCOPE and run_id == "run-1"
        return SimpleNamespace(id="run-1", task_id="task-1", version=7)


def body() -> CompileBusinessInvestigationHandoffRequest:
    return CompileBusinessInvestigationHandoffRequest(
        handoffId="handoff-bi-1",
        approvedPlanRef=plan_ref(),
        sourceSlotId="content.owner",
        targetModuleId="ecommerce.media-studio",
        targetSlotId="content.review",
        purpose="复核方案",
        requestedOutcome="返回受控评审决定",
        markings=["public"],
        expiresAt=NOW + timedelta(minutes=20),
    )


def service(*, projection=None, plans=None):
    compiler, _ = _compiler()
    return EcommerceBusinessInvestigationHandoffService(
        projection=projection or Projection(),
        compilation_receipts=Receipts(),
        plans=plans or Plans(),
        tasks=Tasks(),
        compiler=compiler,
        now=lambda: NOW,
    )


def test_compile_derives_exact_refs_and_emits_zero_side_effect_command() -> None:
    result = service().compile(
        SCOPE,
        "run-1",
        body(),
        roles=["developer"],
        principal_markings=["public"],
    )

    assert result.handoff.readiness == "ready"
    assert result.handoff.source_module_id == "ecommerce.analyst"
    assert result.handoff.target_module_id == "ecommerce.media-studio"
    assert len(result.artifact_refs) == 4
    command = result.handoff.issue_command
    assert command is not None
    assert command.envelope.task_ref.revision == "4"
    assert command.envelope.run_ref.revision == "7"
    assert command.envelope.object_refs[0].content_hash == f"sha256:{HASH}"
    assert all(item.content_hash == f"sha256:{HASH}" for item in command.envelope.artifact_refs)
    assert result.handoff.side_effects.model_dump() == {
        "handoffs_issued": 0,
        "tokens_minted": 0,
        "decisions_created": 0,
        "agent_runs_started": 0,
    }


def test_compile_rejects_stale_plan_and_incomplete_artifact_set() -> None:
    with pytest.raises(BusinessInvestigationHandoffBlocked, match="current"):
        service(plans=Plans(current=False)).compile(
            SCOPE,
            "run-1",
            body(),
            roles=["developer"],
            principal_markings=["public"],
        )
    with pytest.raises(BusinessInvestigationHandoffBlocked, match="four"):
        service(projection=Projection(artifact_count=3)).compile(
            SCOPE,
            "run-1",
            body(),
            roles=["developer"],
            principal_markings=["public"],
        )


def test_request_allows_only_seven_non_analyst_targets() -> None:
    payload = body().model_dump(mode="json", by_alias=True)
    payload["targetModuleId"] = "ecommerce.analyst"
    with pytest.raises(ValueError, match="seven"):
        CompileBusinessInvestigationHandoffRequest.model_validate(payload)
