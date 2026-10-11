"""N5/N6 review-to-content orchestration through a single host command."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aos_extension_sdk import DispatchRef, commit_with_dispatch

from .aip_business_investigation_compiler import canonical_command_hash
from .ecommerce_business_investigation_handoff import build_review_handoff_command
from .ecommerce_business_investigation_review_command import (
    ArtifactBinding,
    ReviewHandoffRequest,
    exact_ref_from_payload,
)
from .sdk_ports import ExactRef, GrowthReviewPort


REVIEW_HANDOFF_OPERATION = "ecommerce_growth_review_advance"
_RECEIPT_FIELDS = frozenset(
    {
        "receiptRef",
        "requestHash",
        "decision",
        "occurrenceRef",
        "caseRef",
        "runRef",
        "analysisReceiptRef",
        "currentPlanRef",
        "reviewIssueRef",
        "evalReportRef",
        "growthPlanRef",
        "artifactBindings",
        "returnStage",
        "handoffRef",
        "taskRef",
        "briefRef",
        "cutoffAt",
        "decidedAt",
        "replayed",
        "sideEffects",
    }
)


def _aware_datetime(value: Any) -> datetime:
    if type(value) is not str:
        raise ValueError("review response cutoff type drifted")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("review response cutoff is invalid") from exc
    if parsed.utcoffset() is None:
        raise ValueError("review response cutoff must include timezone")
    return parsed
_SIDE_EFFECT_FIELDS = frozenset(
    {
        "externalEffectsAllowed",
        "providerInvocationCount",
        "approvalCreatedCount",
        "taskRunCreatedCount",
        "externalPublicationCount",
        "externalBusinessMutationCount",
    }
)


def _artifact_bindings(value: Any) -> tuple[ArtifactBinding, ...]:
    if type(value) is not list or len(value) != 4:
        raise ValueError("review response requires four Artifact bindings")
    result = []
    for item in value:
        if type(item) is not dict or set(item) != {"family", "artifactRef"}:
            raise ValueError("review response Artifact binding fields drifted")
        if type(item["family"]) is not str:
            raise ValueError("review response Artifact family type drifted")
        result.append(
            ArtifactBinding(
                item["family"],
                exact_ref_from_payload(item["artifactRef"], {"ArtifactRevision"}),
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ReviewHandoffReceipt:
    receipt_ref: ExactRef
    request_hash: str
    decision: str
    occurrence_ref: ExactRef
    case_ref: ExactRef
    run_ref: ExactRef
    analysis_receipt_ref: ExactRef
    current_plan_ref: ExactRef
    review_issue_ref: ExactRef
    eval_report_ref: ExactRef
    growth_plan_ref: ExactRef
    artifact_bindings: tuple[ArtifactBinding, ...]
    return_stage: str | None
    handoff_ref: ExactRef | None
    task_ref: ExactRef | None
    brief_ref: ExactRef | None
    cutoff_at: datetime
    decided_at: datetime
    replayed: bool

    @classmethod
    def from_payload(
        cls, value: Any, *, request: ReviewHandoffRequest, request_hash: str
    ) -> "ReviewHandoffReceipt":
        if type(value) is not dict or set(value) != _RECEIPT_FIELDS:
            raise ValueError("review response Receipt fields drifted")
        if value["requestHash"] != request_hash or type(value["decision"]) is not str:
            raise ValueError("review response identity drifted")
        if type(value["replayed"]) is not bool:
            raise ValueError("review response replayed flag drifted")
        side_effects = value["sideEffects"]
        if (
            type(side_effects) is not dict
            or set(side_effects) != _SIDE_EFFECT_FIELDS
            or side_effects["externalEffectsAllowed"] is not False
            or any(
                type(side_effects[field]) is not int or side_effects[field] != 0
                for field in _SIDE_EFFECT_FIELDS - {"externalEffectsAllowed"}
            )
        ):
            raise ValueError("review response side-effect boundary drifted")
        receipt = cls(
            receipt_ref=exact_ref_from_payload(value["receiptRef"], {"ReviewDecisionReceipt"}),
            request_hash=request_hash,
            decision=value["decision"],
            occurrence_ref=exact_ref_from_payload(
                value["occurrenceRef"], {"AutomationOccurrence"}
            ),
            case_ref=exact_ref_from_payload(
                value["caseRef"], {"BusinessInvestigationCaseRevision"}
            ),
            run_ref=exact_ref_from_payload(
                value["runRef"], {"BusinessInvestigationRun"}
            ),
            analysis_receipt_ref=exact_ref_from_payload(
                value["analysisReceiptRef"], {"AnalysisRuntimeReceipt"}
            ),
            current_plan_ref=exact_ref_from_payload(
                value["currentPlanRef"], {"PlanRevision"}
            ),
            review_issue_ref=exact_ref_from_payload(
                value["reviewIssueRef"], {"ReviewIssueRevision"}
            ),
            eval_report_ref=exact_ref_from_payload(
                value["evalReportRef"], {"EvalReportRevision"}
            ),
            growth_plan_ref=exact_ref_from_payload(
                value["growthPlanRef"], {"GrowthPlanRevision"}
            ),
            artifact_bindings=_artifact_bindings(value["artifactBindings"]),
            return_stage=value["returnStage"],
            handoff_ref=exact_ref_from_payload(
                value["handoffRef"], {"HandoffReceipt"}, required=False
            ),
            task_ref=exact_ref_from_payload(value["taskRef"], {"Task"}, required=False),
            brief_ref=exact_ref_from_payload(
                value["briefRef"], {"TaskBriefRevision"}, required=False
            ),
            cutoff_at=_aware_datetime(value["cutoffAt"]),
            decided_at=_aware_datetime(value["decidedAt"]),
            replayed=value["replayed"],
        )
        receipt._validate(request)
        return receipt

    def _validate(self, request: ReviewHandoffRequest) -> None:
        if (
            self.decision != request.decision
            or self.occurrence_ref != request.occurrence_ref
            or self.case_ref != request.case_ref
            or self.run_ref != request.run_ref
            or self.analysis_receipt_ref != request.analysis_receipt_ref
            or self.current_plan_ref != request.current_plan_ref
            or self.review_issue_ref != request.review_issue_ref
            or self.eval_report_ref != request.eval_report_ref
            or self.growth_plan_ref != request.growth_plan_ref
            or self.artifact_bindings != request.artifact_bindings
            or self.cutoff_at != request.cutoff_at
        ):
            raise ValueError("review response exact lineage drifted")
        if self.decided_at < request.cutoff_at:
            raise ValueError("review response decision time precedes cutoff")
        if self.decision == "ACCEPT":
            if (
                self.return_stage is not None
                or self.handoff_ref is None
                or self.task_ref is None
                or self.brief_ref is None
                or request.expires_at is None
                or self.decided_at >= request.expires_at
            ):
                raise ValueError("ACCEPT response requires Handoff, Task and Brief")
        elif self.decision == "RETURN":
            if (
                self.return_stage != request.return_stage
                or self.handoff_ref is not None
                or self.task_ref is not None
                or self.brief_ref is not None
            ):
                raise ValueError("RETURN response cannot create content work")
        else:
            raise ValueError("review response decision drifted")


def advance_review_handoff(
    port: GrowthReviewPort,
    *,
    dispatch_ref: DispatchRef,
    request: ReviewHandoffRequest,
) -> ReviewHandoffReceipt:
    if (
        dispatch_ref.operation_id != REVIEW_HANDOFF_OPERATION
        or dispatch_ref.handler_kind != "extension"
    ):
        raise PermissionError("dispatch does not authorize review Handoff")
    command = build_review_handoff_command(request)
    request_hash = canonical_command_hash(command)
    result = commit_with_dispatch(
        port,
        dispatch_ref,
        {**command, "requestHash": request_hash},
    )
    return ReviewHandoffReceipt.from_payload(
        result,
        request=request,
        request_hash=request_hash,
    )


__all__ = [
    "REVIEW_HANDOFF_OPERATION",
    "ReviewHandoffReceipt",
    "advance_review_handoff",
]
