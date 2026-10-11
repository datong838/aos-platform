"""N4 exact, recoverable analysis orchestration without platform imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aos_extension_sdk import DispatchRef, commit_with_dispatch

from .sdk_ports import ExactRef, GrowthRuntimePort
from .aip_business_investigation_compile_saga import build_start_command
from .aip_business_investigation_compiler import canonical_command_hash
from .aip_business_investigation_data_saga import (
    build_reconcile_command,
    build_resume_data_command,
)
from .aip_business_investigation_runtime import validate_runtime_phase
from .ecommerce_business_investigation_run import AnalysisPhase, RecoverableAction


ANALYSIS_OPERATION = "ecommerce_growth_analysis_advance"
_RUNTIME_MODES = frozenset({"START", "RESUME_DATA", "RECONCILE_UNKNOWN"})
_EVIDENCE_TYPES = {"EvidenceBundleRevision", "DatasetRevision"}
_MAX_EVIDENCE_REFS = 200
_MAX_OBSERVATION_LAG = timedelta(hours=24)
_RECEIPT_FIELDS = frozenset(
    {
        "receiptRef",
        "requestHash",
        "occurrenceRef",
        "caseRef",
        "profileRef",
        "cutoffAt",
        "runRef",
        "compilationRef",
        "planRef",
        "taskRunRef",
        "phase",
        "recoverableAction",
        "checkpointRef",
        "priorCheckpointRef",
        "requirementRef",
        "fulfillmentRef",
        "sourceReadinessRef",
        "mappingRef",
        "evidenceRefs",
        "observedAt",
        "targetReceiptRef",
        "completed",
    }
)


def _ref_payload(ref: ExactRef | None) -> dict[str, object] | None:
    if ref is None:
        return None
    payload: dict[str, object] = {
        "resourceType": ref.resource_type,
        "resourceId": ref.resource_id,
        "revision": ref.revision,
        "contentHash": ref.content_hash,
    }
    if ref.receipt_id is not None:
        payload["receiptId"] = ref.receipt_id
    return payload


def _exact_ref(value: Any, expected: set[str], *, required: bool = True) -> ExactRef | None:
    if value is None and not required:
        return None
    if type(value) is not dict:
        raise ValueError("runtime response is missing an exact reference")
    required_fields = {"resourceType", "resourceId", "revision", "contentHash"}
    if set(value) not in {frozenset(required_fields), frozenset(required_fields | {"receiptId"})}:
        raise ValueError("runtime response exact reference fields drifted")
    ref = ExactRef(
        resource_type=value["resourceType"],
        resource_id=value["resourceId"],
        revision=value["revision"],
        content_hash=value["contentHash"],
        receipt_id=value.get("receiptId"),
    )
    if ref.resource_type not in expected:
        raise ValueError("runtime response exact reference type drifted")
    return ref


def _aware_datetime(value: Any, field: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"runtime response {field} must be an ISO datetime")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError(f"runtime response {field} must include timezone")
    return parsed


@dataclass(frozen=True, slots=True)
class AnalysisRuntimeRequest:
    occurrence_ref: ExactRef
    case_ref: ExactRef
    profile_ref: ExactRef
    cutoff_at: datetime
    idempotency_key: str
    mode: str = "START"
    prior_receipt_ref: ExactRef | None = None
    requirement_ref: ExactRef | None = None
    fulfillment_ref: ExactRef | None = None
    checkpoint_ref: ExactRef | None = None
    prior_plan_ref: ExactRef | None = None
    source_readiness_ref: ExactRef | None = None
    mapping_ref: ExactRef | None = None
    evidence_refs: tuple[ExactRef, ...] = ()
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        expected = (
            (self.occurrence_ref, "AutomationOccurrence"),
            (self.case_ref, "BusinessInvestigationCaseRevision"),
            (self.profile_ref, "InvestigationProfileRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("analysis request contains an invalid exact reference")
        if self.cutoff_at.utcoffset() is None:
            raise ValueError("cutoff_at must include timezone")
        if self.mode not in _RUNTIME_MODES:
            raise ValueError("unsupported analysis runtime mode")
        if not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("idempotency key is required and bounded")
        if self.mode == "START":
            if any(
                ref is not None
                for ref in (
                    self.prior_receipt_ref,
                    self.requirement_ref,
                    self.fulfillment_ref,
                    self.checkpoint_ref,
                    self.prior_plan_ref,
                    self.source_readiness_ref,
                    self.mapping_ref,
                )
            ) or self.evidence_refs or self.observed_at is not None:
                raise ValueError("START cannot claim prior runtime authority")
        elif self.mode == "RESUME_DATA":
            required = (
                (self.prior_receipt_ref, "AnalysisRuntimeReceipt"),
                (self.requirement_ref, "DataRequirementRevision"),
                (self.fulfillment_ref, "DataFulfillmentReceipt"),
                (self.checkpoint_ref, "CheckpointRevision"),
                (self.prior_plan_ref, "PlanRevision"),
                (self.source_readiness_ref, "SourceReadinessEnvelope"),
                (self.mapping_ref, "SourceMappingRevision"),
            )
            if any(ref is None or ref.resource_type != kind for ref, kind in required):
                raise ValueError("RESUME_DATA requires exact prior data and checkpoint refs")
            if (
                type(self.evidence_refs) is not tuple
                or not 1 <= len(self.evidence_refs) <= _MAX_EVIDENCE_REFS
                or any(ref.resource_type not in _EVIDENCE_TYPES for ref in self.evidence_refs)
                or len(set(self.evidence_refs)) != len(self.evidence_refs)
                or self.observed_at is None
                or self.observed_at.utcoffset() is None
                or self.observed_at < self.cutoff_at
                or self.observed_at - self.cutoff_at > _MAX_OBSERVATION_LAG
            ):
                raise ValueError("RESUME_DATA requires exact readiness, mapping and observed evidence")
        else:
            if (
                self.prior_receipt_ref is None
                or self.prior_receipt_ref.resource_type != "AnalysisRuntimeReceipt"
                or self.requirement_ref is not None
                or self.fulfillment_ref is not None
                or self.checkpoint_ref is not None
                or self.prior_plan_ref is not None
                or self.source_readiness_ref is not None
                or self.mapping_ref is not None
                or self.evidence_refs
                or self.observed_at is not None
            ):
                raise ValueError("reconcile requires only an exact prior runtime Receipt")

    def command_payload(self) -> dict[str, object]:
        common = {
            "occurrence_ref": _ref_payload(self.occurrence_ref),
            "case_ref": _ref_payload(self.case_ref),
            "profile_ref": _ref_payload(self.profile_ref),
            "cutoff_at": self.cutoff_at,
            "idempotency_key": self.idempotency_key,
        }
        if self.mode == "START":
            return build_start_command(**common)
        if self.mode == "RESUME_DATA":
            return build_resume_data_command(
                **common,
                prior_receipt_ref=_ref_payload(self.prior_receipt_ref),
                requirement_ref=_ref_payload(self.requirement_ref),
                fulfillment_ref=_ref_payload(self.fulfillment_ref),
                checkpoint_ref=_ref_payload(self.checkpoint_ref),
                prior_plan_ref=_ref_payload(self.prior_plan_ref),
                source_readiness_ref=_ref_payload(self.source_readiness_ref),
                mapping_ref=_ref_payload(self.mapping_ref),
                evidence_refs=tuple(_ref_payload(ref) for ref in self.evidence_refs),
                observed_at=self.observed_at,
            )
        return build_reconcile_command(
            **common,
            prior_receipt_ref=_ref_payload(self.prior_receipt_ref),
            checkpoint_ref=_ref_payload(self.checkpoint_ref),
        )


@dataclass(frozen=True, slots=True)
class AnalysisRuntimeReceipt:
    receipt_ref: ExactRef
    request_hash: str
    occurrence_ref: ExactRef
    case_ref: ExactRef
    profile_ref: ExactRef
    cutoff_at: datetime
    run_ref: ExactRef
    compilation_ref: ExactRef
    plan_ref: ExactRef
    task_run_ref: ExactRef
    phase: AnalysisPhase
    recoverable_action: RecoverableAction
    checkpoint_ref: ExactRef | None
    prior_checkpoint_ref: ExactRef | None
    requirement_ref: ExactRef | None
    fulfillment_ref: ExactRef | None
    source_readiness_ref: ExactRef | None
    mapping_ref: ExactRef | None
    evidence_refs: tuple[ExactRef, ...]
    observed_at: datetime | None
    target_receipt_ref: ExactRef | None
    completed: bool

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        request: AnalysisRuntimeRequest,
        request_hash: str,
    ) -> "AnalysisRuntimeReceipt":
        if type(payload) is not dict or set(payload) != _RECEIPT_FIELDS:
            raise ValueError("runtime response Receipt fields drifted")
        if payload.get("requestHash") != request_hash:
            raise ValueError("runtime response request hash drifted")
        if type(payload["phase"]) is not str or type(payload["recoverableAction"]) is not str:
            raise ValueError("runtime response phase fields drifted")
        if type(payload["evidenceRefs"]) is not list:
            raise ValueError("runtime response evidenceRefs must be a list")
        phase = AnalysisPhase(payload["phase"])
        action = RecoverableAction(payload["recoverableAction"])
        receipt = cls(
            receipt_ref=_exact_ref(payload.get("receiptRef"), {"AnalysisRuntimeReceipt"}),
            request_hash=request_hash,
            occurrence_ref=_exact_ref(payload.get("occurrenceRef"), {"AutomationOccurrence"}),
            case_ref=_exact_ref(payload.get("caseRef"), {"BusinessInvestigationCaseRevision"}),
            profile_ref=_exact_ref(payload.get("profileRef"), {"InvestigationProfileRevision"}),
            cutoff_at=_aware_datetime(payload["cutoffAt"], "cutoffAt"),
            run_ref=_exact_ref(payload.get("runRef"), {"BusinessInvestigationRun"}),
            compilation_ref=_exact_ref(
                payload.get("compilationRef"), {"BusinessInvestigationCompilationReceipt"}
            ),
            plan_ref=_exact_ref(payload.get("planRef"), {"PlanRevision"}),
            task_run_ref=_exact_ref(payload.get("taskRunRef"), {"TaskRun"}),
            phase=phase,
            recoverable_action=action,
            checkpoint_ref=_exact_ref(
                payload.get("checkpointRef"), {"CheckpointRevision"}, required=False
            ),
            prior_checkpoint_ref=_exact_ref(
                payload.get("priorCheckpointRef"), {"CheckpointRevision"}, required=False
            ),
            requirement_ref=_exact_ref(
                payload.get("requirementRef"), {"DataRequirementRevision"}, required=False
            ),
            fulfillment_ref=_exact_ref(
                payload.get("fulfillmentRef"), {"DataFulfillmentReceipt"}, required=False
            ),
            source_readiness_ref=_exact_ref(
                payload.get("sourceReadinessRef"), {"SourceReadinessEnvelope"}, required=False
            ),
            mapping_ref=_exact_ref(
                payload.get("mappingRef"), {"SourceMappingRevision"}, required=False
            ),
            evidence_refs=tuple(
                _exact_ref(item, _EVIDENCE_TYPES)
                for item in payload.get("evidenceRefs", [])
            ),
            observed_at=(
                None
                if payload.get("observedAt") is None
                else _aware_datetime(payload["observedAt"], "observedAt")
            ),
            target_receipt_ref=_exact_ref(
                payload.get("targetReceiptRef"), {"RuntimeCommandReceipt"}, required=False
            ),
            completed=payload.get("completed"),
        )
        receipt._validate(request)
        return receipt

    def _validate(self, request: AnalysisRuntimeRequest) -> None:
        if self.completed is not False:
            raise ValueError("N4 runtime Receipt cannot claim analysis completion")
        if self.cutoff_at.utcoffset() is None or self.cutoff_at != request.cutoff_at:
            raise ValueError("runtime response cutoff drifted")
        if (
            self.occurrence_ref != request.occurrence_ref
            or self.case_ref != request.case_ref
            or self.profile_ref != request.profile_ref
        ):
            raise ValueError("runtime response input lineage drifted")
        validate_runtime_phase(
            mode=request.mode,
            phase=self.phase,
            action=self.recoverable_action,
        )
        if self.phase is AnalysisPhase.WAITING_DATA:
            if (
                self.requirement_ref is None
                or self.checkpoint_ref is None
                or self.fulfillment_ref is not None
                or self.prior_checkpoint_ref is not None
                or self.source_readiness_ref is not None
                or self.mapping_ref is not None
                or self.evidence_refs
                or self.observed_at is not None
                or self.target_receipt_ref is not None
                or self.recoverable_action is not RecoverableAction.WAIT_FOR_DATA
            ):
                raise ValueError("WAITING_DATA runtime lineage is incomplete")
        elif self.phase is AnalysisPhase.RUNNING:
            if self.recoverable_action is not RecoverableAction.CONTINUE:
                raise ValueError("RUNNING must expose CONTINUE")
            if request.mode == "RESUME_DATA" and (
                self.requirement_ref != request.requirement_ref
                or self.fulfillment_ref != request.fulfillment_ref
                or self.source_readiness_ref != request.source_readiness_ref
                or self.mapping_ref != request.mapping_ref
                or self.evidence_refs != request.evidence_refs
                or self.observed_at != request.observed_at
                or self.plan_ref != request.prior_plan_ref
                or self.prior_checkpoint_ref is not None
                or self.target_receipt_ref is not None
                or self.checkpoint_ref != request.checkpoint_ref
            ):
                raise ValueError("resumed runtime data lineage drifted")
            if request.mode == "START" and any(
                value is not None
                for value in (
                    self.requirement_ref,
                    self.fulfillment_ref,
                    self.prior_checkpoint_ref,
                    self.source_readiness_ref,
                    self.mapping_ref,
                    self.observed_at,
                    self.target_receipt_ref,
                )
            ) or (request.mode == "START" and self.evidence_refs):
                raise ValueError("START RUNNING contains incompatible data lineage")
            if request.mode == "RECONCILE_UNKNOWN":
                data_refs = (
                    self.requirement_ref,
                    self.fulfillment_ref,
                    self.prior_checkpoint_ref,
                    self.checkpoint_ref,
                    self.source_readiness_ref,
                    self.mapping_ref,
                )
                empty_lineage = (
                    all(value is None for value in data_refs)
                    and not self.evidence_refs
                    and self.observed_at is None
                )
                complete_lineage = (
                    all(value is not None for value in data_refs)
                    and 1 <= len(self.evidence_refs) <= _MAX_EVIDENCE_REFS
                    and len(set(self.evidence_refs)) == len(self.evidence_refs)
                    and self.observed_at is not None
                    and self.cutoff_at <= self.observed_at
                    and self.observed_at - self.cutoff_at <= _MAX_OBSERVATION_LAG
                    and self.checkpoint_ref.revision
                    == self.prior_checkpoint_ref.revision + 1
                )
                if self.target_receipt_ref is not None or not (
                    empty_lineage or complete_lineage
                ):
                    raise ValueError(
                        "reconciled RUNNING requires empty or complete data lineage"
                    )
        elif self.phase in {AnalysisPhase.UNKNOWN, AnalysisPhase.RECONCILING}:
            if (
                self.target_receipt_ref is None
                or self.recoverable_action is not RecoverableAction.RECONCILE_RECEIPT
            ):
                raise ValueError("unknown runtime must reconcile a target Receipt")
            if any(
                value is not None
                for value in (
                    self.checkpoint_ref,
                    self.prior_checkpoint_ref,
                    self.requirement_ref,
                    self.fulfillment_ref,
                    self.source_readiness_ref,
                    self.mapping_ref,
                    self.observed_at,
                )
            ) or self.evidence_refs:
                raise ValueError("unknown runtime contains incompatible data lineage")
        elif self.recoverable_action is not RecoverableAction.CONTINUE:
            raise ValueError("PREPARING must remain an incomplete continuation")
        elif any(
            value is not None
            for value in (
                self.checkpoint_ref,
                self.prior_checkpoint_ref,
                self.requirement_ref,
                self.fulfillment_ref,
                self.source_readiness_ref,
                self.mapping_ref,
                self.observed_at,
                self.target_receipt_ref,
            )
        ) or self.evidence_refs:
            raise ValueError("PREPARING contains incompatible runtime lineage")


def advance_analysis_runtime(
    port: GrowthRuntimePort,
    *,
    dispatch_ref: DispatchRef,
    request: AnalysisRuntimeRequest,
) -> AnalysisRuntimeReceipt:
    if dispatch_ref.operation_id != ANALYSIS_OPERATION or dispatch_ref.handler_kind != "extension":
        raise PermissionError("dispatch does not authorize analysis runtime")
    command = request.command_payload()
    request_hash = canonical_command_hash(command)
    result = commit_with_dispatch(
        port,
        dispatch_ref,
        {**command, "requestHash": request_hash},
    )
    return AnalysisRuntimeReceipt.from_payload(
        result,
        request=request,
        request_hash=request_hash,
    )


__all__ = [
    "ANALYSIS_OPERATION",
    "AnalysisPhase",
    "AnalysisRuntimeReceipt",
    "AnalysisRuntimeRequest",
    "RecoverableAction",
    "advance_analysis_runtime",
]
