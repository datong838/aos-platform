from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from aos_api.aip_contracts import ExactContractRef, PlanStep, ResourceRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
    canonical_hash,
)
from aos_api.aip_production_contracts import (
    CompileStageTemplateRequest,
    ExactRevisionRef,
    ProductionStartRequest,
    StageApplicability,
    StageDefinition,
)
from aos_api.aip_production_start_service import AipProductionStartService
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


def _exact(kind: str, resource_id: str, content_hash: str = HASH) -> ExactRevisionRef:
    return ExactRevisionRef(
        resourceType=kind,
        resourceId=resource_id,
        revision=1,
        contentHash=content_hash,
    )


def _resource(resource_id: str) -> ResourceRef:
    return ResourceRef(
        resourceType="Schema",
        resourceId=resource_id,
        revision="1",
        authority="aip-schema-registry",
    )


def _stage(
    stage_id: str,
    *,
    depends_on: list[str] | None = None,
    input_schema: str = "shared",
    output_schema: str = "shared",
) -> StageDefinition:
    return StageDefinition(
        stageId=stage_id,
        title=stage_id,
        dependsOn=depends_on or [],
        applicability=StageApplicability(kind="always"),
        requiredSlotIds=["media.review"],
        inputSchemaRef=_resource(input_schema),
        outputSchemaRef=_resource(output_schema),
    )


def _compile_request() -> CompileStageTemplateRequest:
    return CompileStageTemplateRequest(
        taskId="task-1",
        expectedTaskVersion=2,
        templateRevision=1,
        templateContentHash=HASH,
        responsibilityPlanRef=_exact("ResponsibilityPlanRevision", "plan-1"),
        productionContextRef=_exact("ProductionContextRevision", "context-1"),
        profile="STANDARD",
        briefRef=_exact("TaskBriefRevision", "brief-1"),
        evidenceBundleRef=_exact("EvidenceBundleRevision", "evidence-1"),
        evalContractRef=_exact("EvalContractRevision", "eval-1"),
        profileRecommendationRef=_exact(
            "ProfileRecommendationRevision", "recommendation-1"
        ),
        profileConfirmationId="confirmation-1",
        mergePolicyRef=_exact("MergePolicyRevision", "policy-1"),
        capabilityRefs={
            "content.review": _exact("CapabilityRevision", "content.review")
        },
    )


def test_governed_compile_request_requires_complete_exact_contract_set():
    request = _compile_request()
    assert request.capability_refs["content.review"].content_hash == HASH
    with pytest.raises(ValueError, match="complete exact contract set"):
        CompileStageTemplateRequest.model_validate(
            {
                **request.model_dump(mode="json", by_alias=True),
                "profileRecommendationRef": None,
            }
        )
    with pytest.raises(ValueError, match="keys must equal"):
        CompileStageTemplateRequest.model_validate(
            {
                **request.model_dump(mode="json", by_alias=True),
                "capabilityRefs": {
                    "wrong": _exact(
                        "CapabilityRevision", "content.review"
                    ).model_dump(mode="json", by_alias=True)
                },
            }
        )


def test_plan_step_preserves_exact_capability_and_canonical_skip_semantics():
    step = PlanStep(
        stepKey="live",
        title="直播",
        applicability="not_applicable",
        capabilityRefs=[
            ExactContractRef(
                resourceType="CapabilityRevision",
                resourceId="live.orchestrate",
                revision=1,
                contentHash=HASH,
            )
        ],
        responsibilitySlotIds=["media.director"],
        inputSchemaRef=_resource("input"),
        outputSchemaRef=_resource("output"),
        skipReason="PROFILE_NOT_APPLICABLE:STANDARD",
    )
    assert step.capability_refs[0].resource_id == "live.orchestrate"
    with pytest.raises(ValueError, match="requires skipReason"):
        PlanStep(stepKey="live", title="直播", applicability="not_applicable")


def test_stage_topology_is_normalized_and_cycles_or_unknowns_fail_closed():
    ordered = AipProductionContractStore._normalized_stage_order(
        [_stage("render", depends_on=["plan"]), _stage("plan"), _stage("audit")]
    )
    assert [item.stage_id for item in ordered] == ["audit", "plan", "render"]
    with pytest.raises(ProductionContractDependencyBlocked, match="UNKNOWN"):
        AipProductionContractStore._normalized_stage_order(
            [_stage("render", depends_on=["missing"])]
        )
    with pytest.raises(ProductionContractDependencyBlocked, match="CYCLE"):
        AipProductionContractStore._normalized_stage_order(
            [_stage("a", depends_on=["b"]), _stage("b", depends_on=["a"])]
        )


class _Rows:
    def __init__(self, row: Any):
        self._row = row

    def fetchone(self):
        return self._row


class _GovernedConnection:
    def __init__(self, request: CompileStageTemplateRequest):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert request.profile_recommendation_ref is not None
        assert request.merge_policy_ref is not None
        self.rows = {
            "confirmation": {
                "recommendation_id": request.profile_recommendation_ref.resource_id,
                "recommendation_revision": request.profile_recommendation_ref.revision,
                "recommendation_hash": request.profile_recommendation_ref.content_hash,
                "selected_profile": request.profile,
                "policy_ref": request.merge_policy_ref.model_dump(
                    mode="json", by_alias=True
                ),
                "selected_template_ref": _exact(
                    "ResponsibilityTemplateRevision", "responsibility-template-1"
                ).model_dump(mode="json", by_alias=True),
                "content_hash": HASH,
            },
            "recommendation": {
                "content_hash": request.profile_recommendation_ref.content_hash,
                "readiness": "ready",
                "expires_at": future,
            },
            "policy": {
                "content_hash": request.merge_policy_ref.content_hash,
                "expires_at": future,
            },
        }

    def execute(self, sql: str, _params: tuple[Any, ...]):
        if "confirmation_receipt" in sql:
            return _Rows(self.rows["confirmation"])
        if "recommendation_revision" in sql:
            return _Rows(self.rows["recommendation"])
        if "merge_policy_revision" in sql:
            return _Rows(self.rows["policy"])
        raise AssertionError(sql)


def test_governed_snapshot_binds_confirmation_and_context_exact_refs():
    request = _compile_request()
    plan = SimpleNamespace(
        profile_recommendation_ref=request.profile_recommendation_ref,
        profile_confirmation_id=request.profile_confirmation_id,
        merge_policy_ref=request.merge_policy_ref,
        template_ref=_exact(
            "ResponsibilityTemplateRevision", "responsibility-template-1"
        ),
    )
    context = SimpleNamespace(
        brief_ref=request.brief_ref,
        evidence_bundle_ref=request.evidence_bundle_ref,
        eval_contract_ref=request.eval_contract_ref,
    )
    snapshot = AipProductionContractStore()._governed_compilation_snapshot(
        _GovernedConnection(request), SCOPE, request, plan, context
    )
    assert [item["resourceType"] for item in snapshot[:6]] == [
        "TaskBriefRevision",
        "EvidenceBundleRevision",
        "EvalContractRevision",
        "ProfileRecommendationRevision",
        "ProfileConfirmationReceipt",
        "MergePolicyRevision",
    ]


class _PlanConnection:
    def __init__(self, plan: dict[str, Any]):
        self.plan = plan

    def execute(self, _sql: str, _params: tuple[Any, ...]):
        return _Rows(self.plan)


def test_start_gate_detects_w7_compilation_envelope_drift():
    steps = [{"stepKey": "plan", "title": "计划"}]
    dependencies: list[dict[str, str]] = []
    governed = [{"resourceType": f"T{index}"} for index in range(7)]
    production_contract = {
        "compilerVersion": "w7c.v1",
        "stageTemplateRef": _exact(
            "StageTemplateRevision", "stage-1"
        ).model_dump(mode="json", by_alias=True),
        "responsibilityPlanRef": _exact(
            "ResponsibilityPlanRevision", "responsibility-1"
        ).model_dump(mode="json", by_alias=True),
        "productionContextRef": _exact(
            "ProductionContextRevision", "context-1"
        ).model_dump(mode="json", by_alias=True),
        "governedDependencies": governed,
        "normalizedStageIds": ["plan"],
        "productionStartGateRequired": True,
        "productionStartGateRef": None,
    }
    input_hash = canonical_hash(
        {
            "compilerVersion": production_contract["compilerVersion"],
            "templateRef": production_contract["stageTemplateRef"],
            "responsibilityPlanRef": production_contract["responsibilityPlanRef"],
            "productionContextRef": production_contract["productionContextRef"],
            "governedDependencies": governed,
            "normalizedStageIds": production_contract["normalizedStageIds"],
        }
    )
    compilation_hash = canonical_hash(
        {"inputHash": input_hash, "steps": steps, "dependencies": dependencies}
    )
    production_contract.update(
        {"inputHash": input_hash, "compilationHash": compilation_hash}
    )
    production_context_ref = _exact("ProductionContextRevision", "context-1")
    plan_ref = _exact("PlanRevision", "plan-1")
    plan = {
        "task_id": "task-1",
        "plan_revision_id": "plan-1",
        "revision": 1,
        "content_hash": HASH,
        "approval_status": "draft",
        "steps": steps,
        "dependencies": dependencies,
        "risk": {"productionContract": production_contract},
    }
    body = ProductionStartRequest(
        taskId="task-1",
        expectedTaskVersion=2,
        productionContextRef=production_context_ref,
        planRef=plan_ref,
        previewRef=_exact("ImpactPreviewRevision", "preview-1"),
        actionProposalRef={
            "proposalId": "proposal-1",
            "version": 1,
            "proposalHash": HASH,
        },
        logicGraphId="logic-1",
        logicRevision=1,
        logicGraphHash=HASH,
    )
    task = {
        "version": 2,
        "status": "planning",
        "current_plan_revision_id": "plan-1",
    }
    blockers: list[Any] = []
    AipProductionStartService()._check_plan(
        _PlanConnection(plan), SCOPE, body, task, [], blockers
    )
    assert blockers == []

    plan["risk"]["productionContract"]["compilationHash"] = "f" * 64
    blockers = []
    AipProductionStartService()._check_plan(
        _PlanConnection(plan), SCOPE, body, task, [], blockers
    )
    assert [item.code for item in blockers] == [
        "PLAN_W7_COMPILATION_ENVELOPE_DRIFTED"
    ]

    plan["risk"]["productionContract"]["compilationHash"] = compilation_hash
    plan["risk"]["productionContract"]["governedDependencies"][0] = {
        "resourceType": "tampered"
    }
    blockers = []
    AipProductionStartService()._check_plan(
        _PlanConnection(plan), SCOPE, body, task, [], blockers
    )
    assert [item.code for item in blockers] == [
        "PLAN_W7_COMPILATION_ENVELOPE_DRIFTED"
    ]
