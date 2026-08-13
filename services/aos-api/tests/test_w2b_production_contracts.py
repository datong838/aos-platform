from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contracts import (
    AssigneeKind,
    AssigneeRef,
    CreateEvalContractRequest,
    CreateResponsibilityPlanRequest,
    ExactRevisionRef,
    MergeDecision,
    ResponsibilitySlot,
)


def exact(resource_type: str, resource_id: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=resource_type,
        resource_id=resource_id,
        revision=1,
        content_hash="a" * 64,
    )


def schema(name: str) -> ResourceRef:
    return ResourceRef(
        resource_type="Schema",
        resource_id=name,
        revision="1",
        authority="aip",
    )


def slot(slot_id: str = "content.review") -> ResponsibilitySlot:
    return ResponsibilitySlot(
        slot_id=slot_id,
        responsibility_type="independent_review",
        required_capability_ids=["capability.content.review"],
        input_schema_ref=schema("content.review.input"),
        output_schema_ref=schema("content.review.output"),
        gate_refs=[exact("EvalContractRevision", "eval-content")],
        return_stage="draft",
        assignee=AssigneeRef(
            kind=AssigneeKind.AGENT_INSTANCE,
            resource_id="agent-content",
            version=1,
        ),
    )


def test_eval_contract_is_strict_and_thresholds_are_bounded() -> None:
    request = CreateEvalContractRequest(
        suite_ref=exact("EvalSuiteRevision", "suite-content"),
        artifact_schema_ref=schema("content.artifact"),
        severity_thresholds={"critical": 1.0, "warning": 0.7},
        gate_policy={"mode": "all"},
        return_mapping={"critical": "draft"},
        override_policy={"allowed": False},
    )
    assert request.suite_ref.resource_type == "EvalSuiteRevision"
    with pytest.raises(ValidationError):
        CreateEvalContractRequest.model_validate(
            {**request.model_dump(by_alias=True), "unknownField": True}
        )
    with pytest.raises(ValidationError):
        CreateEvalContractRequest.model_validate(
            {**request.model_dump(by_alias=True), "severityThresholds": {"critical": 1.1}}
        )


def test_responsibility_plan_rejects_duplicate_slots_and_protected_merge() -> None:
    with pytest.raises(ValidationError, match="slot IDs must be unique"):
        CreateResponsibilityPlanRequest(
            profile="standard",
            template_ref=exact("ResponsibilityTemplateRevision", "content-standard"),
            slots=[slot(), slot()],
        )
    with pytest.raises(ValidationError, match="protected responsibility"):
        MergeDecision(
            source_slot_ids=["content.review"],
            target_slot_id="content.coordination",
            reason="same agent",
            merged_responsibility_types=["independent_review"],
        )


def test_readiness_is_not_accepted_from_client() -> None:
    payload = {
        "profile": "standard",
        "templateRef": exact("ResponsibilityTemplateRevision", "content-standard").model_dump(by_alias=True),
        "slots": [slot().model_dump(by_alias=True)],
        "readiness": "ready",
    }
    with pytest.raises(ValidationError):
        CreateResponsibilityPlanRequest.model_validate(payload)
