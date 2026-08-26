"""BI-W8-04 Workshop adapter over canonical AIP ReviewIssue authority."""

from __future__ import annotations

import hashlib
from typing import Literal, Protocol, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_eval_runner import AipEvalRunner
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import (
    ExactRevisionRef,
    ResolveReviewIssueRequest,
    ReturnDecision,
    ReturnReviewIssueRequest,
    ReviewIssue,
    ReviewIssueStatus,
)
from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceiptStore,
)
from aos_api.aip_business_investigation_runtime import CanonicalRuntimeRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionReader,
    BusinessInvestigationProjectionSource,
    CanonicalBusinessInvestigationProjectionReader,
)
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.tenant_scope import TenantScope


ReviewDecision = Literal["accept", "return", "request_more"]
InvestigationStage = Literal["portrait", "diagnosis", "solution_design"]


class BusinessInvestigationStageReviewCommand(AipContractModel):
    decision: ReviewDecision
    issue_id: str = Field(min_length=1, max_length=200)
    expected_issue_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("issue_id", "reason")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned != value or not cleaned:
            raise ValueError("review command strings must be trimmed and non-blank")
        return cleaned


class BusinessInvestigationStageReviewItem(AipContractModel):
    issue: ReviewIssue
    stage: InvestigationStage
    eval_report_ref: ExactRevisionRef
    artifact_ref: ExactRevisionRef
    allowed_decisions: list[Literal["accept", "return"]] = Field(max_length=2)

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        expected = ["accept", "return"] if self.issue.status is ReviewIssueStatus.OPEN else []
        if self.allowed_decisions != expected:
            raise ValueError("allowedDecisions drifted from canonical ReviewIssue")
        if self.eval_report_ref != self.issue.eval_report_ref:
            raise ValueError("EvalReport exact ref drifted")
        if (
            self.artifact_ref.resource_type != "Artifact"
            or self.artifact_ref.resource_id != self.issue.artifact_ref.artifact_id
            or self.artifact_ref.revision != 1
            or self.artifact_ref.content_hash != self.issue.artifact_ref.content_hash
        ):
            raise ValueError("Artifact exact ref drifted")
        return self


class BusinessInvestigationStageReviewProjection(AipContractModel):
    tenant: TenantContext
    run_ref: InvestigationExactRef
    task_run_ref: CanonicalRuntimeRef
    items: list[BusinessInvestigationStageReviewItem] = Field(max_length=100)
    external_effects_allowed: Literal[False] = False


class BusinessInvestigationStageReviewResponse(AipContractModel):
    tenant: TenantContext
    decision: Literal["accept", "return"]
    issue: ReviewIssue
    return_decision: ReturnDecision | None = None
    replayed_outcome_possible: Literal[True] = True
    external_effects_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _decision_shape(self) -> Self:
        if (self.decision == "return") != (self.return_decision is not None):
            raise ValueError("review response decision shape drifted")
        return self


class BusinessInvestigationReviewCommandBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ReviewAuthority(Protocol):
    def list_review_issues(self, scope: TenantScope): ...
    def get_review_issue(self, scope: TenantScope, issue_id: str) -> ReviewIssue: ...
    def resolve_review_issue(
        self, scope: TenantScope, actor: str, issue_id: str, key: str,
        body: ResolveReviewIssueRequest,
    ) -> ReviewIssue: ...
    def return_review_issue(
        self, scope: TenantScope, actor: str, issue_id: str, key: str,
        body: ReturnReviewIssueRequest,
    ) -> ReturnDecision: ...


class EvalReportReader(Protocol):
    def get_report(
        self, scope: TenantScope, report_id: str, revision: int = 1
    ) -> EvalReportRevision: ...


class EcommerceBusinessInvestigationReviewCommandService:
    """Resolve one Run to canonical AIP review authority without copying state."""

    def __init__(
        self,
        *,
        run_store: BusinessInvestigationRunStore | None = None,
        case_store: BusinessInvestigationCaseStore | None = None,
        receipt_store: BusinessInvestigationCompilationReceiptStore | None = None,
        projection_reader: BusinessInvestigationProjectionReader | None = None,
        reviews: ReviewAuthority | None = None,
        reports: EvalReportReader | None = None,
    ) -> None:
        self._runs = run_store or BusinessInvestigationRunStore()
        self._cases = case_store or BusinessInvestigationCaseStore()
        self._receipts = receipt_store or BusinessInvestigationCompilationReceiptStore()
        self._projection = projection_reader or CanonicalBusinessInvestigationProjectionReader()
        self._reviews = reviews or AipProductionContractStore()
        self._reports = reports or AipEvalRunner()

    def projection(
        self, scope: TenantScope, run_id: str
    ) -> BusinessInvestigationStageReviewProjection:
        source, task_run_id = self._runtime_source(scope, run_id)
        items: list[BusinessInvestigationStageReviewItem] = []
        for issue in self._reviews.list_review_issues(scope).items:
            report = self._reports.get_report(
                scope,
                issue.eval_report_ref.resource_id,
                issue.eval_report_ref.revision,
            )
            if report.stage_attempt_ref is None or report.stage_attempt_ref.run_id != task_run_id:
                continue
            self._validate_issue_report(issue, report)
            items.append(self._item(issue, report))
        items.sort(key=lambda item: (item.issue.updated_at, item.issue.issue_id), reverse=True)
        assert source.runtime is not None and source.runtime.task_run_version is not None
        return BusinessInvestigationStageReviewProjection(
            tenant=self._tenant(scope),
            run_ref=self._run_ref(source),
            task_run_ref=CanonicalRuntimeRef(
                resource_type="TaskRun",
                resource_id=task_run_id,
                version=source.runtime.task_run_version,
            ),
            items=items,
        )

    def review_stage(
        self,
        scope: TenantScope,
        run_id: str,
        command: BusinessInvestigationStageReviewCommand,
        *,
        expected_state_version: int,
        idempotency_key: str,
        actor: str,
    ) -> BusinessInvestigationStageReviewResponse:
        actor = actor.strip()
        key = idempotency_key.strip()
        if not actor or not key or len(key) > 200:
            raise ValueError("actor and Idempotency-Key are required")
        if command.decision == "request_more":
            raise BusinessInvestigationReviewCommandBlocked(
                "REQUEST_MORE_CANONICAL_AUTHORITY_UNAVAILABLE"
            )
        source, task_run_id = self._runtime_source(scope, run_id)
        if source.state.version != expected_state_version:
            raise BusinessInvestigationReviewCommandBlocked("RUN_STATE_VERSION_DRIFTED")
        issue = self._reviews.get_review_issue(scope, command.issue_id)
        if issue.version != command.expected_issue_version:
            raise BusinessInvestigationReviewCommandBlocked("ISSUE_VERSION_DRIFTED")
        report = self._reports.get_report(
            scope, issue.eval_report_ref.resource_id, issue.eval_report_ref.revision
        )
        if report.stage_attempt_ref is None or report.stage_attempt_ref.run_id != task_run_id:
            raise BusinessInvestigationReviewCommandBlocked("ISSUE_RUN_LINEAGE_DRIFTED")
        self._validate_issue_report(issue, report)
        if command.decision == "accept":
            resolved = self._reviews.resolve_review_issue(
                scope,
                actor,
                issue.issue_id,
                key,
                ResolveReviewIssueRequest(
                    expected_version=issue.version,
                    reason=command.reason,
                    resolution_refs=[
                        issue.eval_report_ref,
                        ExactRevisionRef(
                            resource_type="Artifact",
                            resource_id=issue.artifact_ref.artifact_id,
                            revision=1,
                            content_hash=issue.artifact_ref.content_hash,
                        ),
                    ],
                ),
            )
            return BusinessInvestigationStageReviewResponse(
                tenant=self._tenant(scope), decision="accept", issue=resolved
            )
        decision = self._reviews.return_review_issue(
            scope,
            actor,
            issue.issue_id,
            key,
            ReturnReviewIssueRequest(
                expected_version=issue.version,
                run_id=task_run_id,
                target_stage=issue.return_stage,
                reason=command.reason,
                attempt_idempotency_key=self._attempt_key(key),
            ),
        )
        returned = self._reviews.get_review_issue(scope, issue.issue_id)
        return BusinessInvestigationStageReviewResponse(
            tenant=self._tenant(scope),
            decision="return",
            issue=returned,
            return_decision=decision,
        )

    def _runtime_source(
        self, scope: TenantScope, run_id: str
    ) -> tuple[BusinessInvestigationProjectionSource, str]:
        run = self._runs.get(scope, run_id)
        case = self._cases.get(scope, run.authority.case_ref.resource_id)
        if (
            case.revision != run.authority.case_ref.revision
            or case.content_hash != run.authority.case_ref.content_hash
        ):
            raise BusinessInvestigationReviewCommandBlocked("RUN_CASE_REF_DRIFTED")
        run_ref = InvestigationExactRef(
            resource_type="BusinessInvestigationRun",
            resource_id=run.authority.run_id,
            revision=run.authority.version,
            content_hash=run.authority.content_hash,
        )
        receipt = self._receipts.get_for_run(scope, run_ref)
        source = self._projection.read(scope, run_id)
        runtime = source.runtime
        if (
            runtime is None
            or runtime.task_run_id is None
            or runtime.task_run_version is None
            or runtime.task_id != receipt.task_id
            or runtime.plan_ref.resource_id != receipt.plan_ref.resource_id
            or runtime.plan_ref.revision != receipt.plan_ref.revision
            or runtime.plan_ref.content_hash != f"sha256:{receipt.plan_ref.content_hash}"
        ):
            raise BusinessInvestigationReviewCommandBlocked("RUNTIME_LINEAGE_DRIFTED")
        return source, runtime.task_run_id

    @staticmethod
    def _validate_issue_report(issue: ReviewIssue, report: EvalReportRevision) -> None:
        if (
            report.report_id != issue.eval_report_ref.resource_id
            or report.revision != issue.eval_report_ref.revision
            or report.content_hash != issue.eval_report_ref.content_hash
        ):
            raise BusinessInvestigationReviewCommandBlocked("ISSUE_EVAL_REF_DRIFTED")
        subject = report.subject_artifact_ref
        if (
            subject is None
            or subject.resource_id != issue.artifact_ref.artifact_id
            or subject.content_hash != issue.artifact_ref.content_hash
        ):
            raise BusinessInvestigationReviewCommandBlocked("ISSUE_ARTIFACT_REF_DRIFTED")
        if report.stage_attempt_ref is None or report.stage_attempt_ref.step_key not in {
            "portrait", "diagnosis", "solution_design"
        }:
            raise BusinessInvestigationReviewCommandBlocked("ISSUE_STAGE_DRIFTED")

    @staticmethod
    def _item(
        issue: ReviewIssue, report: EvalReportRevision
    ) -> BusinessInvestigationStageReviewItem:
        assert report.stage_attempt_ref is not None
        return BusinessInvestigationStageReviewItem(
            issue=issue,
            stage=report.stage_attempt_ref.step_key,
            eval_report_ref=issue.eval_report_ref,
            artifact_ref=ExactRevisionRef(
                resource_type="Artifact",
                resource_id=issue.artifact_ref.artifact_id,
                revision=1,
                content_hash=issue.artifact_ref.content_hash,
            ),
            allowed_decisions=(
                ["accept", "return"] if issue.status is ReviewIssueStatus.OPEN else []
            ),
        )

    @staticmethod
    def _run_ref(source: BusinessInvestigationProjectionSource) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type="BusinessInvestigationRun",
            resource_id=source.run.run_id,
            revision=source.run.version,
            content_hash=source.run.content_hash,
        )

    @staticmethod
    def _attempt_key(key: str) -> str:
        return "bi-review-return-" + hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)
