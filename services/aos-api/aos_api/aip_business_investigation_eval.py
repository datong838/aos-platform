"""BI-W5-06 three-stage coordinator over canonical Eval and Review authority."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinding
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_eval_contracts import (
    EvalContractRevisionRef,
    EvalGatePolicyRef,
    EvalReportRevision,
    EvalStageAttemptRef,
    EvalSubjectArtifactRef,
)
from aos_api.aip_production_contracts import (
    CreateReviewIssueRequest,
    ExactRevisionRef,
    ReturnDecision,
    ReturnReviewIssueRequest,
    ReviewIssue,
)
from aos_api.tenant_scope import TenantScope


InvestigationStage = Literal["portrait", "diagnosis", "solution_design"]


class BusinessInvestigationStageEvalRequest(AipContractModel):
    stage: InvestigationStage
    idempotency_key: str = Field(min_length=1, max_length=200)
    eval_contract_ref: EvalContractRevisionRef
    subject_artifact_ref: EvalSubjectArtifactRef
    stage_attempt_ref: EvalStageAttemptRef
    gate_policy_ref: EvalGatePolicyRef
    evidence_cutoff_at: datetime

    @field_validator("idempotency_key")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("idempotencyKey must not be blank")
        return cleaned

    @field_validator("evidence_cutoff_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("evidenceCutoffAt requires timezone")
        return value

    @model_validator(mode="after")
    def _stage_matches_attempt(self) -> BusinessInvestigationStageEvalRequest:
        if self.stage_attempt_ref.step_key != self.stage:
            raise ValueError("stageAttemptRef stepKey must match stage")
        return self


class BusinessInvestigationStageQualityGate(AipContractModel):
    stage: InvestigationStage
    eval_report_ref: ExactRevisionRef
    subject_artifact_ref: EvalSubjectArtifactRef
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(gt=0)
    pass_rate: float = Field(ge=0, le=1)
    gate_passed: bool
    automatic_promotion_allowed: Literal[False] = False
    next_allowed_commands: list[str] = Field(default_factory=list)


class BusinessInvestigationEvalBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EvalRunner(Protocol):
    def run_by_contract(self, scope: TenantScope, **kwargs: Any) -> EvalReportRevision: ...


class ReviewAuthority(Protocol):
    def create_review_issue(
        self, scope: TenantScope, actor: str, key: str, body: CreateReviewIssueRequest
    ) -> ReviewIssue: ...

    def return_review_issue(
        self,
        scope: TenantScope,
        actor: str,
        issue_id: str,
        key: str,
        body: ReturnReviewIssueRequest,
    ) -> ReturnDecision: ...


class BusinessInvestigationEvalCoordinator:
    def __init__(self, runner: EvalRunner, reviews: ReviewAuthority) -> None:
        self._runner = runner
        self._reviews = reviews

    def evaluate_stage(
        self,
        scope: TenantScope,
        runtime: BusinessInvestigationRuntimeBinding,
        request: BusinessInvestigationStageEvalRequest,
        actor: str,
        *,
        created_at: datetime,
        resolve_artifact: Any,
        execute_target: Any,
        execute_judge: Any,
    ) -> BusinessInvestigationStageQualityGate:
        self._runtime_guard(scope, runtime)
        if request.stage_attempt_ref.run_id != runtime.task_run_ref.resource_id:
            raise BusinessInvestigationEvalBlocked("STAGE_ATTEMPT_RUN_DRIFTED")
        if created_at.utcoffset() is None:
            raise ValueError("created_at requires timezone")
        if request.evidence_cutoff_at > created_at:
            raise BusinessInvestigationEvalBlocked("EVIDENCE_CUTOFF_IN_FUTURE")
        actor = actor.strip()
        if not actor:
            raise ValueError("actor is required")
        report = self._runner.run_by_contract(
            scope,
            contract_id=request.eval_contract_ref.resource_id,
            contract_revision=request.eval_contract_ref.revision,
            contract_content_hash=request.eval_contract_ref.content_hash,
            idempotency_key=request.idempotency_key,
            actor=actor,
            resolve_artifact=resolve_artifact,
            execute_target=execute_target,
            execute_judge=execute_judge,
            subject_artifact_ref=request.subject_artifact_ref,
            stage_attempt_ref=request.stage_attempt_ref,
            gate_policy_ref=request.gate_policy_ref,
            evidence_cutoff_at=request.evidence_cutoff_at,
        )
        self._report_guard(scope, request, report)
        report_ref = ExactRevisionRef(
            resource_type="EvalReportRevision",
            resource_id=report.report_id,
            revision=report.revision,
            content_hash=report.content_hash,
        )
        return BusinessInvestigationStageQualityGate(
            stage=request.stage,
            eval_report_ref=report_ref,
            subject_artifact_ref=request.subject_artifact_ref,
            passed=report.passed,
            failed=report.failed,
            total=report.total,
            pass_rate=report.pass_rate,
            gate_passed=report.gate_passed,
            next_allowed_commands=(
                ["request-human-stage-decision"]
                if report.gate_passed
                else ["open-review-issue"]
            ),
        )

    def open_review_issue(
        self,
        scope: TenantScope,
        gate: BusinessInvestigationStageQualityGate,
        actor: str,
        idempotency_key: str,
        body: CreateReviewIssueRequest,
    ) -> ReviewIssue:
        if gate.gate_passed:
            raise BusinessInvestigationEvalBlocked("PASSED_GATE_CANNOT_AUTO_OPEN_ISSUE")
        if body.eval_report_ref != gate.eval_report_ref:
            raise BusinessInvestigationEvalBlocked("ISSUE_REPORT_DRIFTED")
        if (
            body.artifact_ref.artifact_id != gate.subject_artifact_ref.resource_id
            or body.artifact_ref.content_hash
            != gate.subject_artifact_ref.content_hash
        ):
            raise BusinessInvestigationEvalBlocked("ISSUE_ARTIFACT_DRIFTED")
        if body.return_stage != gate.stage:
            raise BusinessInvestigationEvalBlocked("ISSUE_STAGE_DRIFTED")
        return self._reviews.create_review_issue(
            scope, actor.strip(), idempotency_key.strip(), body
        )

    def return_review_issue(
        self,
        scope: TenantScope,
        runtime: BusinessInvestigationRuntimeBinding,
        issue: ReviewIssue,
        actor: str,
        idempotency_key: str,
        body: ReturnReviewIssueRequest,
    ) -> ReturnDecision:
        self._runtime_guard(scope, runtime)
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if issue.tenant != tenant:
            raise BusinessInvestigationEvalBlocked("ISSUE_TENANT_DRIFTED")
        if body.run_id != runtime.task_run_ref.resource_id:
            raise BusinessInvestigationEvalBlocked("RETURN_RUN_DRIFTED")
        if body.target_stage != issue.return_stage:
            raise BusinessInvestigationEvalBlocked("RETURN_STAGE_DRIFTED")
        return self._reviews.return_review_issue(
            scope, actor.strip(), issue.issue_id, idempotency_key.strip(), body
        )

    @staticmethod
    def _runtime_guard(
        scope: TenantScope, runtime: BusinessInvestigationRuntimeBinding
    ) -> None:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if runtime.tenant != tenant:
            raise BusinessInvestigationEvalBlocked("RUNTIME_TENANT_MISMATCH")
        if runtime.checkpoint_ref is None:
            raise BusinessInvestigationEvalBlocked("CHECKPOINT_REQUIRED")

    @staticmethod
    def _report_guard(
        scope: TenantScope,
        request: BusinessInvestigationStageEvalRequest,
        report: EvalReportRevision,
    ) -> None:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if report.tenant != tenant:
            raise BusinessInvestigationEvalBlocked("REPORT_TENANT_DRIFTED")
        if report.eval_contract_ref != request.eval_contract_ref:
            raise BusinessInvestigationEvalBlocked("REPORT_CONTRACT_DRIFTED")
        if report.subject_artifact_ref != request.subject_artifact_ref:
            raise BusinessInvestigationEvalBlocked("REPORT_ARTIFACT_DRIFTED")
        if report.stage_attempt_ref != request.stage_attempt_ref:
            raise BusinessInvestigationEvalBlocked("REPORT_ATTEMPT_DRIFTED")
        if report.gate_policy_ref != request.gate_policy_ref:
            raise BusinessInvestigationEvalBlocked("REPORT_POLICY_DRIFTED")
        if report.evidence_cutoff_at != request.evidence_cutoff_at:
            raise BusinessInvestigationEvalBlocked("REPORT_CUTOFF_DRIFTED")
