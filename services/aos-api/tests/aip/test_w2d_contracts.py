from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contracts import (
    ActionProposalExactRef,
    BriefLifecycle,
    ContractBlocker,
    ContractReadiness,
    CreateImpactPreviewRequest,
    ExactRevisionRef,
    ImpactAssessment,
    ImpactDimension,
    ImpactPreviewRevision,
    ImpactQuality,
    MutableAuthorityRef,
    ProductionStartDecision,
    ProductionStartDecisionStatus,
    ProductionStartRequest,
)


HASH = "a" * 64
OTHER_HASH = "b" * 64
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def exact(resource_type: str, resource_id: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=resource_type,
        resource_id=resource_id,
        revision=1,
        content_hash=HASH,
    )


def source(resource_type: str = "Evidence") -> ResourceRef:
    return ResourceRef(
        resource_type=resource_type,
        resource_id="source-1",
        revision="1",
        authority="aip-evidence-authority",
    )


def measured(value: object) -> ImpactDimension:
    return ImpactDimension(
        quality=ImpactQuality.MEASURED,
        value=value,
        source_refs=[source()],
        cutoff_at=NOW,
    )


def assessment() -> ImpactAssessment:
    return ImpactAssessment(
        object_scope=measured({"count": 10}),
        channel_scope=measured({"channels": ["weapp"]}),
        cost=measured({"currency": "CNY", "amount": "10.00"}),
        budget=measured({"currency": "CNY", "remaining": "90.00"}),
        risks=measured([{"code": "BATCH_SEND", "level": "medium"}]),
        reversibility=measured({"reversible": True}),
        approval_chain=measured({"minimumApprovals": 1}),
        rate_capacity_kill=measured({"capacity": 100, "killSwitch": False}),
    )


def create_request(**overrides: object) -> CreateImpactPreviewRequest:
    values: dict[str, object] = {
        "task_id": "task-1",
        "plan_ref": exact("PlanRevision", "plan-1"),
        "brief_ref": exact("TaskBriefRevision", "brief-1"),
        "evidence_bundle_ref": exact("EvidenceBundleRevision", "bundle-1"),
        "eval_contract_ref": exact("EvalContractRevision", "eval-1"),
        "responsibility_plan_ref": exact("ResponsibilityPlanRevision", "responsibility-1"),
        "stage_template_ref": exact("StageTemplateRevision", "stage-1"),
        "model_route_ref": exact("ModelRouteRevision", "route-1"),
        "runtime_policy_ref": exact("RuntimePolicyRevision", "policy-1"),
        "binding_refs": [
            MutableAuthorityRef(
                resource_type="CapabilityBinding",
                resource_id="binding-1",
                version=2,
            )
        ],
        "capability_ref": exact("CapabilityRevision", "copy.generate"),
        "account_ref": MutableAuthorityRef(
            resource_type="ShopAccountBinding",
            resource_id="account-1",
            version=1,
        ),
        "impact": assessment(),
        "expires_at": NOW,
    }
    values.update(overrides)
    return CreateImpactPreviewRequest.model_validate(values)


def proposal_ref() -> ActionProposalExactRef:
    return ActionProposalExactRef(
        proposal_id="proposal-1",
        version=1,
        proposal_hash=OTHER_HASH,
    )


def test_impact_preview_contract_accepts_exact_authorities_and_quality() -> None:
    request = create_request()
    payload = request.model_dump(mode="json", by_alias=True)
    assert payload["planRef"]["resourceType"] == "PlanRevision"
    assert payload["impact"]["cost"]["quality"] == "measured"
    assert payload["bindingRefs"][0]["version"] == 2


@pytest.mark.parametrize(
    ("dimension", "message"),
    [
        (
            {"quality": "unknown", "value": 0},
            "unknown impact dimension cannot carry a value",
        ),
        (
            {"quality": "measured", "value": 1},
            "measured or estimated impact dimension requires sourceRefs",
        ),
    ],
)
def test_impact_dimension_fails_closed_on_false_certainty(
    dimension: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ImpactDimension.model_validate(dimension)


def test_preview_rejects_wrong_ref_kind_and_half_runtime_pair() -> None:
    with pytest.raises(ValidationError, match="briefRef must reference TaskBriefRevision"):
        create_request(brief_ref=exact("Task", "brief-1"))
    with pytest.raises(
        ValidationError,
        match="modelRouteRef and runtimePolicyRef must be supplied together",
    ):
        create_request(runtime_policy_ref=None)


def test_preview_rejects_duplicate_or_uncontrolled_bindings() -> None:
    binding = MutableAuthorityRef(
        resource_type="CapabilityBinding", resource_id="binding-1", version=1
    )
    with pytest.raises(ValidationError, match="bindingRefs must be unique"):
        create_request(binding_refs=[binding, binding])
    with pytest.raises(ValidationError, match="bindingRefs must reference"):
        create_request(
            binding_refs=[
                MutableAuthorityRef(
                    resource_type="DisplayName", resource_id="content-agent", version=1
                )
            ]
        )


def test_frozen_preview_requires_actor_and_timestamp() -> None:
    values = {
        **create_request().model_dump(mode="python"),
        "tenant": TenantContext(org_id="org-org", project_id="dev-project"),
        "preview_id": "preview-1",
        "revision": 1,
        "version": 1,
        "content_hash": HASH,
        "dependency_snapshot_hash": OTHER_HASH,
        "lifecycle": BriefLifecycle.FROZEN,
        "readiness": ContractReadiness.READY,
        "blockers": [],
        "created_by": "maker-1",
        "created_at": NOW,
    }
    with pytest.raises(ValidationError, match="only frozen ImpactPreview revisions"):
        ImpactPreviewRevision.model_validate(values)
    frozen = ImpactPreviewRevision.model_validate(
        {**values, "frozen_by": "approver-1", "frozen_at": NOW}
    )
    assert frozen.lifecycle is BriefLifecycle.FROZEN


def test_preview_rejects_partial_freeze_or_ambiguous_readiness() -> None:
    values = {
        **create_request().model_dump(mode="python"),
        "tenant": TenantContext(org_id="org-org", project_id="dev-project"),
        "preview_id": "preview-1",
        "revision": 1,
        "version": 1,
        "content_hash": HASH,
        "dependency_snapshot_hash": OTHER_HASH,
        "lifecycle": BriefLifecycle.DRAFT,
        "readiness": ContractReadiness.READY,
        "blockers": [],
        "created_by": "maker-1",
        "created_at": NOW,
    }
    with pytest.raises(ValidationError, match="frozenBy and frozenAt must be supplied together"):
        ImpactPreviewRevision.model_validate({**values, "frozen_by": "approver-1"})
    with pytest.raises(ValidationError, match="ready ImpactPreview revision cannot carry blockers"):
        ImpactPreviewRevision.model_validate(
            {
                **values,
                "blockers": [
                    ContractBlocker(code="AIP_PROVIDER_NOT_READY", message="provider missing")
                ],
            }
        )
    with pytest.raises(ValidationError, match="non-ready ImpactPreview revision requires blockers"):
        ImpactPreviewRevision.model_validate(
            {**values, "readiness": ContractReadiness.BLOCKED}
        )


def test_start_request_requires_plan_and_preview_exact_kinds() -> None:
    with pytest.raises(ValidationError, match="previewRef must reference ImpactPreviewRevision"):
        ProductionStartRequest(
            task_id="task-1",
            expected_task_version=1,
            plan_ref=exact("PlanRevision", "plan-1"),
            preview_ref=exact("Artifact", "preview-1"),
            action_proposal_ref=proposal_ref(),
            logic_graph_id="logic-1",
            logic_revision=1,
        )


def decision_values(status: ProductionStartDecisionStatus) -> dict[str, object]:
    return {
        "tenant": TenantContext(org_id="org-org", project_id="dev-project"),
        "decision_id": "start-decision-1",
        "status": status,
        "task_id": "task-1",
        "plan_ref": exact("PlanRevision", "plan-1"),
        "preview_ref": exact("ImpactPreviewRevision", "preview-1"),
        "action_proposal_ref": proposal_ref(),
        "dependency_snapshot_hash": HASH,
        "created_by": "operator-1",
        "created_at": NOW,
    }


def test_start_decision_never_confuses_blocked_with_started() -> None:
    blocker = ContractBlocker(code="AIP_PROVIDER_NOT_READY", message="provider missing")
    with pytest.raises(ValidationError, match="started decision requires taskRunRef"):
        ProductionStartDecision.model_validate(
            {**decision_values(ProductionStartDecisionStatus.STARTED), "blockers": []}
        )
    blocked = ProductionStartDecision.model_validate(
        {
            **decision_values(ProductionStartDecisionStatus.BLOCKED),
            "blockers": [blocker],
        }
    )
    assert blocked.task_run_ref is None
    started = ProductionStartDecision.model_validate(
        {
            **decision_values(ProductionStartDecisionStatus.STARTED),
            "blockers": [],
            "task_run_ref": ResourceRef(
                resource_type="TaskRun",
                resource_id="run-1",
                revision="1",
                authority="aip-task-runtime",
            ),
        }
    )
    assert started.status is ProductionStartDecisionStatus.STARTED


def test_non_started_decision_cannot_carry_task_run() -> None:
    blocker = ContractBlocker(code="AIP_ROUTE_NOT_READY", message="route missing")
    with pytest.raises(ValidationError, match="cannot carry taskRunRef"):
        ProductionStartDecision.model_validate(
            {
                **decision_values(ProductionStartDecisionStatus.UNKNOWN),
                "blockers": [blocker],
                "task_run_ref": ResourceRef(
                    resource_type="TaskRun",
                    resource_id="run-1",
                    revision="1",
                    authority="aip-task-runtime",
                ),
            }
        )
