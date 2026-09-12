"""Strict no-effect messages for the installed growth review operation."""

from datetime import datetime
from hashlib import sha256
import json
import re

from .ecommerce_analyst_authority_contracts import AnalystExactRef, TenantContext
from .ecommerce_analyst_stage_decision import AssigneeRef, AnalystStageDecisionRevision, EvalStageAttemptRef
from .ecommerce_analyst_stage_eval_report import (
    EvalContractRevisionRef, EvalGatePolicyRef, EvalSubjectArtifactRef,
    StageEvalReportProof, require_stage_eval_report_inputs,
)
from .ecommerce_analyst_stage_review_authority import require_stage_review_slot
from .ecommerce_analyst_stage_review_command import require_stage_review_command_identity
from .ecommerce_analyst_stage_review_runtime import (
    require_observed_stage_subject, require_stage_runtime_references,
)
from .analyst_structure_case import structure_case_from_query


def _exact(payload, keys):
    if type(payload) is not dict or set(payload) != set(keys):
        raise ValueError("exact stage review message required")


def _hash(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    return sha256(raw.encode()).hexdigest()


def handle_stage_review_message(payload: dict[str, object]) -> dict[str, object]:
    kind = payload.get("kind")
    if kind == "validate_command_identity":
        _exact(payload, ("kind", "tenant", "item", "actor", "key", "expectedVersion"))
        item = require_stage_review_command_identity(
            tenant=TenantContext.model_validate(payload["tenant"]),
            item=AnalystStageDecisionRevision.model_validate(payload["item"]),
            actor=payload["actor"], key=payload["key"], expected_version=payload["expectedVersion"],
        )
        return {"decisionRef": {"resourceType": "AnalystStageDecisionRevision", "resourceId": item.decision_id,
            "revision": item.revision, "contentHash": item.content_hash}}
    if kind == "validate_review_slot":
        _exact(payload, ("kind", "stage", "actor", "slotId", "responsibilityType",
            "requiredCapabilityIds", "returnStage", "assignee", "assigneeResolutionReceiptId"))
        assignee = require_stage_review_slot(stage=payload["stage"], actor=payload["actor"],
            slot_id=payload["slotId"], responsibility_type=payload["responsibilityType"],
            required_capability_ids=payload["requiredCapabilityIds"], return_stage=payload["returnStage"],
            assignee=AssigneeRef.model_validate(payload["assignee"]),
            assignee_resolution_receipt_id=payload["assigneeResolutionReceiptId"])
        return {"assignee": assignee.model_dump(mode="json", by_alias=True)}
    if kind == "validate_runtime":
        _exact(payload, ("kind", "taskRunId", "planRef", "stage", "stageAttemptRef", "subjectRef", "observationPayload"))
        attempt=EvalStageAttemptRef.model_validate(payload["stageAttemptRef"])
        subject=AnalystExactRef.model_validate(payload["subjectRef"])
        require_stage_runtime_references(task_run_id=payload["taskRunId"], plan_ref=AnalystExactRef.model_validate(payload["planRef"]),
            stage=payload["stage"], stage_attempt_ref=attempt, subject_ref=subject)
        require_observed_stage_subject(stage=payload["stage"], step_run_id=attempt.step_run_id,
            subject_ref=subject, observation_payload=payload["observationPayload"])
        return {"subjectRef": subject.model_dump(mode="json", by_alias=True)}
    if kind == "validate_eval_proof":
        _exact(payload, ("kind", "proof", "tenant", "artifactRef", "stageAttemptRef", "evalContractRef", "gatePolicyRef", "cutoffAt", "now"))
        proof=StageEvalReportProof.model_validate(payload["proof"])
        require_stage_eval_report_inputs(proof=proof, tenant=TenantContext.model_validate(payload["tenant"]),
            artifact_ref=EvalSubjectArtifactRef.model_validate(payload["artifactRef"]),
            stage_attempt_ref=EvalStageAttemptRef.model_validate(payload["stageAttemptRef"]),
            eval_contract_ref=EvalContractRevisionRef.model_validate(payload["evalContractRef"]),
            gate_policy_ref=EvalGatePolicyRef.model_validate(payload["gatePolicyRef"]),
            cutoff_at=datetime.fromisoformat(payload["cutoffAt"]), now=datetime.fromisoformat(payload["now"]))
        return {"reportRef": proof.report_ref.model_dump(mode="json", by_alias=True)}
    if kind == "validate_structure_case":
        _exact(payload,("kind","query","stage","expectedCaseInputHash"))
        expected=payload["expectedCaseInputHash"]
        if type(expected) is not str or re.fullmatch(r"[0-9a-f]{64}",expected) is None:
            raise ValueError("exact structure case hash required")
        actual=_hash(structure_case_from_query(payload["query"],stage=payload["stage"]))
        if actual!=expected:
            raise ValueError("structure case differs from Eval input")
        return {"caseInputHash":actual}
    raise ValueError("unknown stage review message")


__all__ = ["handle_stage_review_message"]
