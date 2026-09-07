"""N4 exact, recoverable analysis orchestration without platform imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

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
    if not isinstance(value, Mapping):
        raise ValueError("runtime response is missing an exact reference")
    ref = ExactRef(
        resource_type=str(value.get("resourceType", "")),
        resource_id=str(value.get("resourceId", "")),
        revision=value.get("revision"),
        content_hash=str(value.get("contentHash", "")),
        receipt_id=None if value.get("receiptId") is None else str(value["receiptId"]),
    )
    if ref.resource_type not in expected:
        raise ValueError("runtime response exact reference type drifted")
    return ref


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
                )
            ):
                raise ValueError("START cannot claim prior runtime authority")
        elif self.mode == "RESUME_DATA":
            required = (
                (self.prior_receipt_ref, "AnalysisRuntimeReceipt"),
                (self.requirement_ref, "DataRequirementRevision"),
                (self.fulfillment_ref, "DataFulfillmentReceipt"),
                (self.checkpoint_ref, "CheckpointRevision"),
            )
            if any(ref is None or ref.resource_type != kind for ref, kind in required):
                raise ValueError("RESUME_DATA requires exact prior data and checkpoint refs")
        else:
            if (
                self.prior_receipt_ref is None
                or self.prior_receipt_ref.resource_type != "AnalysisRuntimeReceipt"
                or self.requirement_ref is not None
                or self.fulfillment_ref is not None
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
    requirement_ref: ExactRef | None
    fulfillment_ref: ExactRef | None
    target_receipt_ref: ExactRef | None
    completed: bool

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        request: AnalysisRuntimeRequest,
        request_hash: str,
    ) -> "AnalysisRuntimeReceipt":
        if not isinstance(payload, Mapping) or payload.get("requestHash") != request_hash:
            raise ValueError("runtime response request hash drifted")
        phase = AnalysisPhase(str(payload.get("phase", "")))
        action = RecoverableAction(str(payload.get("recoverableAction", "")))
        receipt = cls(
            receipt_ref=_exact_ref(payload.get("receiptRef"), {"AnalysisRuntimeReceipt"}),
            request_hash=request_hash,
            occurrence_ref=_exact_ref(payload.get("occurrenceRef"), {"AutomationOccurrence"}),
            case_ref=_exact_ref(payload.get("caseRef"), {"BusinessInvestigationCaseRevision"}),
            profile_ref=_exact_ref(payload.get("profileRef"), {"InvestigationProfileRevision"}),
            cutoff_at=datetime.fromisoformat(str(payload.get("cutoffAt", ""))),
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
            requirement_ref=_exact_ref(
                payload.get("requirementRef"), {"DataRequirementRevision"}, required=False
            ),
            fulfillment_ref=_exact_ref(
                payload.get("fulfillmentRef"), {"DataFulfillmentReceipt"}, required=False
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
                or self.recoverable_action is not RecoverableAction.WAIT_FOR_DATA
            ):
                raise ValueError("WAITING_DATA runtime lineage is incomplete")
        elif self.phase is AnalysisPhase.RUNNING:
            if self.recoverable_action is not RecoverableAction.CONTINUE:
                raise ValueError("RUNNING must expose CONTINUE")
            if request.mode == "RESUME_DATA" and (
                self.requirement_ref != request.requirement_ref
                or self.fulfillment_ref != request.fulfillment_ref
                or self.checkpoint_ref is None
            ):
                raise ValueError("resumed runtime data lineage drifted")
        elif self.phase in {AnalysisPhase.UNKNOWN, AnalysisPhase.RECONCILING}:
            if (
                self.target_receipt_ref is None
                or self.recoverable_action is not RecoverableAction.RECONCILE_RECEIPT
            ):
                raise ValueError("unknown runtime must reconcile a target Receipt")
        elif self.recoverable_action is not RecoverableAction.CONTINUE:
            raise ValueError("PREPARING must remain an incomplete continuation")


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
