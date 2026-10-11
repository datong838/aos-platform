"""N5 exact review command; persistence remains host-owned."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import unicodedata

from .ecommerce_content_campaign_workflow_contracts import ContentTaskSpec
from .ecommerce_analyst_authority_contracts import AnalystExactRef
from .ecommerce_analyst_stage_decision import EvalStageAttemptRef
from .sdk_ports import ExactRef


ARTIFACT_FAMILIES = ("portrait", "diagnosis", "growth_plan", "evidence_summary")
_CJK = re.compile(r"[\u3400-\u9fff]")
_TECHNICAL_POLLUTION = re.compile(
    r"(?:(?:AR|W|R|N)\s*[-_]?\s*\d|技术方案|开发任务|波次|API|SQL|DDL|数据库迁移|代码|(?:/[\w.-]+){2,}|(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|sql|md|json|ya?ml)|[A-Za-z]:\\+[^\\\s]+(?:\\+[^\\\s]+)+)",
    re.IGNORECASE,
)


def exact_ref_payload(ref: ExactRef | None) -> dict[str, object] | None:
    if ref is None:
        return None
    value: dict[str, object] = {
        "resourceType": ref.resource_type,
        "resourceId": ref.resource_id,
        "revision": ref.revision,
        "contentHash": ref.content_hash,
    }
    if ref.receipt_id is not None:
        value["receiptId"] = ref.receipt_id
    return value


def exact_ref_from_payload(value, expected: set[str], *, required: bool = True) -> ExactRef | None:
    if value is None and not required:
        return None
    if type(value) is not dict:
        raise ValueError("review response is missing an exact reference")
    base = {"resourceType", "resourceId", "revision", "contentHash"}
    if set(value) not in {frozenset(base), frozenset(base | {"receiptId"})}:
        raise ValueError("review response exact reference fields drifted")
    ref = ExactRef(
        resource_type=value["resourceType"],
        resource_id=value["resourceId"],
        revision=value["revision"],
        content_hash=value["contentHash"],
        receipt_id=value.get("receiptId"),
    )
    if ref.resource_type not in expected:
        raise ValueError("review response exact reference type drifted")
    return ref


@dataclass(frozen=True, slots=True)
class ArtifactBinding:
    family: str
    artifact_ref: ExactRef

    def __post_init__(self) -> None:
        if self.family not in ARTIFACT_FAMILIES:
            raise ValueError("unsupported investigation Artifact family")
        if self.artifact_ref.resource_type != "ArtifactRevision":
            raise ValueError("artifact binding requires ArtifactRevision")

    def payload(self) -> dict[str, object]:
        return {"family": self.family, "artifactRef": exact_ref_payload(self.artifact_ref)}


@dataclass(frozen=True, slots=True)
class ReviewHandoffRequest:
    occurrence_ref: ExactRef
    case_ref: ExactRef
    run_ref: ExactRef
    analysis_receipt_ref: ExactRef
    current_plan_ref: ExactRef
    growth_plan_ref: ExactRef
    review_issue_ref: ExactRef
    eval_report_ref: ExactRef
    artifact_bindings: tuple[ArtifactBinding, ...]
    decision: str
    idempotency_key: str
    cutoff_at: datetime
    growth_plan_status: str = "APPROVED"
    growth_plan_current: bool = True
    review_issue_status: str = "OPEN"
    return_stage: str | None = None
    target_module_id: str | None = None
    source_slot_id: str | None = None
    target_slot_id: str | None = None
    markings: tuple[str, ...] = ()
    expires_at: datetime | None = None
    content_task: ContentTaskSpec | None = None

    def __post_init__(self) -> None:
        expected = (
            (self.occurrence_ref, "AutomationOccurrence"),
            (self.case_ref, "BusinessInvestigationCaseRevision"),
            (self.run_ref, "BusinessInvestigationRun"),
            (self.analysis_receipt_ref, "AnalysisRuntimeReceipt"),
            (self.current_plan_ref, "PlanRevision"),
            (self.growth_plan_ref, "GrowthPlanRevision"),
            (self.review_issue_ref, "ReviewIssueRevision"),
            (self.eval_report_ref, "EvalReportRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("review command contains an invalid exact reference")
        if type(self.cutoff_at) is not datetime or self.cutoff_at.utcoffset() is None:
            raise ValueError("review cutoff must include timezone")
        if type(self.idempotency_key) is not str or not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("review idempotency key is required and bounded")
        if (
            self.growth_plan_status != "APPROVED"
            or self.growth_plan_current is not True
            or self.review_issue_status != "OPEN"
        ):
            raise ValueError("review requires current APPROVED plan and OPEN issue")
        if type(self.artifact_bindings) is not tuple or tuple(
            item.family for item in self.artifact_bindings
        ) != ARTIFACT_FAMILIES:
            raise ValueError("review requires four Artifacts in canonical family order")
        if len({item.artifact_ref for item in self.artifact_bindings}) != 4:
            raise ValueError("review Artifact refs must be unique")
        if self.decision == "REQUEST_MORE":
            raise ValueError("REQUEST_MORE has no canonical authority")
        if self.decision not in {"ACCEPT", "RETURN"}:
            raise ValueError("unsupported review decision")
        if self.decision == "RETURN":
            if self.return_stage not in {"portrait", "diagnosis", "solution_design"}:
                raise ValueError("RETURN requires a canonical target stage")
            if type(self.markings) is not tuple or any(
                value is not None
                for value in (
                    self.target_module_id,
                    self.source_slot_id,
                    self.target_slot_id,
                    self.expires_at,
                    self.content_task,
                )
            ) or self.markings:
                raise ValueError("RETURN cannot create Handoff or content work")
            return
        if self.return_stage is not None:
            raise ValueError("ACCEPT cannot contain a return stage")
        if (
            self.target_module_id != "ecommerce.content-campaign"
            or self.source_slot_id != "analyst.solution"
            or self.target_slot_id != "content.plan"
            or self.markings != ("internal",)
            or type(self.expires_at) is not datetime
            or self.expires_at.utcoffset() is None
            or not self.cutoff_at < self.expires_at <= self.cutoff_at + timedelta(days=7)
            or self.content_task is None
            or self.content_task.growth_plan_ref != self.growth_plan_ref
            or self.content_task.artifact_refs
            != tuple(item.artifact_ref for item in self.artifact_bindings)
        ):
            raise ValueError("ACCEPT requires an exact bounded content Handoff")
        for value in self.content_task.business_text_values():
            normalized = "".join(
                character
                for character in unicodedata.normalize("NFKC", value)
                if unicodedata.category(character) != "Cf"
            )
            if not _CJK.search(normalized) or _TECHNICAL_POLLUTION.search(normalized):
                raise ValueError("content Task and Brief fields must be Chinese business text")

    def command_payload(self) -> dict[str, object]:
        task = self.content_task
        return {
            "operation": "review_handoff.advance",
            "occurrenceRef": exact_ref_payload(self.occurrence_ref),
            "caseRef": exact_ref_payload(self.case_ref),
            "runRef": exact_ref_payload(self.run_ref),
            "analysisReceiptRef": exact_ref_payload(self.analysis_receipt_ref),
            "currentPlanRef": exact_ref_payload(self.current_plan_ref),
            "growthPlanRef": exact_ref_payload(self.growth_plan_ref),
            "reviewIssueRef": exact_ref_payload(self.review_issue_ref),
            "evalReportRef": exact_ref_payload(self.eval_report_ref),
            "artifactBindings": [item.payload() for item in self.artifact_bindings],
            "decision": self.decision,
            "returnStage": self.return_stage,
            "targetModuleId": self.target_module_id,
            "sourceSlotId": self.source_slot_id,
            "targetSlotId": self.target_slot_id,
            "markings": list(self.markings),
            "expiresAt": None if self.expires_at is None else self.expires_at.isoformat(),
            "taskSpec": None
            if task is None
            else {
                "taskType": "ecommerce.workshop.business_task",
                "briefType": "content_campaign",
                "title": task.title,
                "objective": task.objective,
                "channels": list(task.channels),
                "audience": task.audience,
                "timeWindow": task.time_window,
                "constraints": list(task.constraints),
                "growthPlanRef": exact_ref_payload(task.growth_plan_ref),
                "artifactRefs": [exact_ref_payload(ref) for ref in task.artifact_refs],
            },
            "cutoffAt": self.cutoff_at.isoformat(),
            "idempotencyKey": self.idempotency_key,
        }


@dataclass(frozen=True, slots=True)
class AcceptedStageHandoffRequest:
    """Package-owned exact proposal; current Host still refuses its execution."""

    occurrence_ref: ExactRef
    case_ref: ExactRef
    run_ref: ExactRef
    analysis_receipt_ref: ExactRef
    current_plan_ref: ExactRef
    growth_plan_ref: ExactRef
    eval_report_ref: ExactRef
    stage_decision_ref: AnalystExactRef
    stage_task_run_id: str
    stage_plan_ref: AnalystExactRef
    stage_attempt_ref: EvalStageAttemptRef
    stage_artifact_ref: AnalystExactRef
    responsibility_plan_ref: AnalystExactRef
    cutoff_at: datetime
    expires_at: datetime
    idempotency_key: str
    content_task: ContentTaskSpec

    def __post_init__(self) -> None:
        for value, kind, model in (
            (self.occurrence_ref, "AutomationOccurrence", ExactRef),
            (self.case_ref, "BusinessInvestigationCaseRevision", ExactRef),
            (self.run_ref, "BusinessInvestigationRun", ExactRef),
            (self.analysis_receipt_ref, "AnalysisRuntimeReceipt", ExactRef),
            (self.current_plan_ref, "PlanRevision", ExactRef),
            (self.growth_plan_ref, "GrowthPlanRevision", ExactRef),
            (self.eval_report_ref, "EvalReportRevision", ExactRef),
            (self.stage_decision_ref, "AnalystStageDecisionRevision", AnalystExactRef),
            (self.stage_plan_ref, "PlanRevision", AnalystExactRef),
            (self.stage_artifact_ref, "Artifact", AnalystExactRef),
            (self.responsibility_plan_ref, "ResponsibilityPlanRevision", AnalystExactRef),
        ):
            if type(value) is not model or value.resource_type != kind:
                raise ValueError("accepted stage Handoff exact reference type drifted")
        if (type(self.stage_attempt_ref) is not EvalStageAttemptRef
                or type(self.stage_task_run_id) is not str or not self.stage_task_run_id
                or self.stage_task_run_id != self.stage_task_run_id.strip()
                or self.stage_attempt_ref.run_id != self.stage_task_run_id
                or self.stage_attempt_ref.step_key not in {"solution-design", "solution_design"}
                or self.current_plan_ref.resource_id != self.stage_plan_ref.resource_id
                or self.current_plan_ref.revision != self.stage_plan_ref.revision
                or self.current_plan_ref.content_hash != "sha256:" + self.stage_plan_ref.content_hash):
            raise ValueError("accepted stage Handoff runtime source drifted")
        if (type(self.cutoff_at) is not datetime or self.cutoff_at.utcoffset() is None
                or type(self.expires_at) is not datetime or self.expires_at.utcoffset() is None
                or not self.cutoff_at < self.expires_at <= self.cutoff_at + timedelta(days=7)
                or type(self.idempotency_key) is not str
                or self.idempotency_key != self.idempotency_key.strip()
                or not 1 <= len(self.idempotency_key) <= 200):
            raise ValueError("accepted stage Handoff lifetime or idempotency drifted")
        if (type(self.content_task) is not ContentTaskSpec
                or self.content_task.source_kind != "accepted-stage-v1"
                or self.content_task.growth_plan_ref != self.growth_plan_ref
                or self.content_task.artifact_refs != (ExactRef(
                    "Artifact", self.stage_artifact_ref.resource_id,
                    self.stage_artifact_ref.revision,
                    "sha256:" + self.stage_artifact_ref.content_hash),)):
            raise ValueError("accepted stage Handoff Task source drifted")
        for value in self.content_task.business_text_values():
            normalized = "".join(ch for ch in unicodedata.normalize("NFKC", value)
                                 if unicodedata.category(ch) != "Cf")
            if (normalized != value or value != value.strip()
                    or not _CJK.search(value) or _TECHNICAL_POLLUTION.search(value)):
                raise ValueError("accepted stage Handoff requires Chinese business text")

    def command_payload(self) -> dict[str, object]:
        task = self.content_task
        return {
            "operation": "review_handoff.advance",
            "sourceKind": "accepted-stage-v1",
            "occurrenceRef": exact_ref_payload(self.occurrence_ref),
            "caseRef": exact_ref_payload(self.case_ref),
            "runRef": exact_ref_payload(self.run_ref),
            "analysisReceiptRef": exact_ref_payload(self.analysis_receipt_ref),
            "currentPlanRef": exact_ref_payload(self.current_plan_ref),
            "growthPlanRef": exact_ref_payload(self.growth_plan_ref),
            "evalReportRef": exact_ref_payload(self.eval_report_ref),
            "stageDecisionRef": self.stage_decision_ref.model_dump(mode="json", by_alias=True),
            "stageTaskRunId": self.stage_task_run_id,
            "stagePlanRef": self.stage_plan_ref.model_dump(mode="json", by_alias=True),
            "stageAttemptRef": self.stage_attempt_ref.model_dump(mode="json", by_alias=True),
            "stageArtifactRef": self.stage_artifact_ref.model_dump(mode="json", by_alias=True),
            "responsibilityPlanRef": self.responsibility_plan_ref.model_dump(mode="json", by_alias=True),
            "decision": "ACCEPT",
            "returnStage": None,
            "targetModuleId": "ecommerce.content-campaign",
            "sourceSlotId": "analyst.solution",
            "targetSlotId": "content.plan",
            "markings": ["internal"],
            "expiresAt": self.expires_at.isoformat(),
            "taskSpec": {
                "taskType": "ecommerce.workshop.business_task",
                "briefType": "content_campaign",
                "title": task.title,
                "objective": task.objective,
                "channels": list(task.channels),
                "audience": task.audience,
                "timeWindow": task.time_window,
                "constraints": list(task.constraints),
                "growthPlanRef": exact_ref_payload(task.growth_plan_ref),
                "artifactRefs": [exact_ref_payload(ref) for ref in task.artifact_refs],
            },
            "cutoffAt": self.cutoff_at.isoformat(),
            "idempotencyKey": self.idempotency_key,
        }


__all__ = [
    "AcceptedStageHandoffRequest",
    "ARTIFACT_FAMILIES",
    "ArtifactBinding",
    "ReviewHandoffRequest",
    "exact_ref_from_payload",
    "exact_ref_payload",
]
