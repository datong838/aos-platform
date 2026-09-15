"""Minimal stage Eval proof; full report and current execution stay host-owned."""

from datetime import datetime
from typing import Literal

from pydantic import Field, StrictInt, model_validator

from .ecommerce_analyst_authority_contracts import (
    AipContractModel,
    AnalystExactRef,
    TenantContext,
)
from .ecommerce_analyst_stage_decision import EvalStageAttemptRef


class EvalContractRevisionRef(AipContractModel):
    resource_type: Literal["EvalContractRevision"] = "EvalContractRevision"
    resource_id: str = Field(min_length=1, max_length=200)
    revision: StrictInt = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvalSubjectArtifactRef(AipContractModel):
    resource_type: Literal["Artifact"] = "Artifact"
    resource_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvalGatePolicyRef(AipContractModel):
    resource_type: Literal["MediaGatePolicyRevision"] = "MediaGatePolicyRevision"
    resource_id: str = Field(min_length=1, max_length=200)
    revision: StrictInt = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class StageEvalReportProof(AipContractModel):
    tenant: TenantContext
    report_ref: AnalystExactRef
    eval_contract_ref: EvalContractRevisionRef
    subject_artifact_ref: EvalSubjectArtifactRef
    stage_attempt_ref: EvalStageAttemptRef
    gate_policy_ref: EvalGatePolicyRef
    evidence_cutoff_at: datetime
    gate_passed: bool
    created_at: datetime

    @model_validator(mode="after")
    def _valid_stage_proof(self):
        if (
            self.report_ref.resource_type != "EvalReportRevision"
            or not self.gate_passed
            or self.created_at.utcoffset() is None
            or self.evidence_cutoff_at.utcoffset() is None
            or self.evidence_cutoff_at > self.created_at
        ):
            raise ValueError("stage eval report is not a valid passed exact report")
        return self


def require_stage_eval_report_inputs(
    *,
    proof: StageEvalReportProof,
    tenant: TenantContext,
    artifact_ref: EvalSubjectArtifactRef,
    stage_attempt_ref: EvalStageAttemptRef,
    eval_contract_ref: EvalContractRevisionRef,
    gate_policy_ref: EvalGatePolicyRef,
    cutoff_at: datetime,
    now: datetime,
) -> None:
    if not isinstance(proof, StageEvalReportProof):
        raise TypeError("stage Eval proof required")
    proof = StageEvalReportProof.model_validate(proof.model_dump(mode="python"))
    if (
        not isinstance(now, datetime)
        or now.utcoffset() is None
        or proof.created_at > now
        or proof.tenant != tenant
        or proof.subject_artifact_ref != artifact_ref
        or proof.stage_attempt_ref != stage_attempt_ref
        or proof.eval_contract_ref != eval_contract_ref
        or proof.gate_policy_ref != gate_policy_ref
        or proof.evidence_cutoff_at != cutoff_at
    ):
        raise ValueError("stage eval report inputs drifted")


__all__ = [
    "EvalContractRevisionRef",
    "EvalGatePolicyRef",
    "EvalSubjectArtifactRef",
    "StageEvalReportProof",
    "require_stage_eval_report_inputs",
]
