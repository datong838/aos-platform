"""AR2-4 package-owned recoverable analysis runtime contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"
GROWTH_ROOT = ROOT / "bundles/solutions/ecommerce-growth/backend"
for dependency in (SDK_ROOT, GROWTH_ROOT):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from aos_extension_sdk import DispatchRef
from ecommerce_growth.analysis_runtime import (
    ANALYSIS_OPERATION,
    AnalysisRuntimeRequest,
    advance_analysis_runtime,
)
from ecommerce_growth.ecommerce_business_investigation_application import (
    EcommerceGrowthApplication,
)
from ecommerce_growth.sdk_ports import ExactRef


HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
CUTOFF = datetime(2026, 9, 8, 0, tzinfo=UTC)


def ref(kind: str, identity: str, *, revision: int = 1, receipt: str | None = None) -> ExactRef:
    return ExactRef(kind, identity, revision, HASH_A, receipt)


def dispatch(*, operation: str = ANALYSIS_OPERATION, epoch: int = 7, org: str = "org-org") -> DispatchRef:
    return DispatchRef.from_payload(
        {
            "orgId": org,
            "projectId": "dev-project",
            "operationId": operation,
            "handlerKind": "extension",
            "dispatchRevision": 11,
            "installationId": "11111111-1111-4111-8111-111111111111",
            "generation": "22222222-2222-4222-8222-222222222222",
            "executionEpoch": epoch,
            "cutoverGroupId": "33333333-3333-4333-8333-333333333333",
            "cutoverGroupRevision": 5,
        }
    )


def start_request(*, key: str = "occurrence-start-1") -> AnalysisRuntimeRequest:
    return AnalysisRuntimeRequest(
        occurrence_ref=ref("AutomationOccurrence", "occurrence-1"),
        case_ref=ref("BusinessInvestigationCaseRevision", "case-1"),
        profile_ref=ref("InvestigationProfileRevision", "profile-1"),
        cutoff_at=CUTOFF,
        idempotency_key=key,
    )


def exact_payload(item: ExactRef) -> dict[str, object]:
    payload = {
        "resourceType": item.resource_type,
        "resourceId": item.resource_id,
        "revision": item.revision,
        "contentHash": item.content_hash,
    }
    if item.receipt_id:
        payload["receiptId"] = item.receipt_id
    return payload


def receipt_payload(command, *, phase="PREPARING", action="CONTINUE", **overrides):
    payload = {
        "receiptRef": exact_payload(ref("AnalysisRuntimeReceipt", "runtime-receipt-1")),
        "requestHash": command["requestHash"],
        "occurrenceRef": command["occurrenceRef"],
        "caseRef": command["caseRef"],
        "profileRef": command["profileRef"],
        "cutoffAt": command["cutoffAt"],
        "runRef": exact_payload(ref("BusinessInvestigationRun", "run-1")),
        "compilationRef": exact_payload(
            ref("BusinessInvestigationCompilationReceipt", "compilation-1")
        ),
        "planRef": exact_payload(ref("PlanRevision", "plan-1")),
        "taskRunRef": exact_payload(ref("TaskRun", "task-run-1")),
        "phase": phase,
        "recoverableAction": action,
        "checkpointRef": None,
        "requirementRef": None,
        "fulfillmentRef": None,
        "targetReceiptRef": None,
        "completed": False,
    }
    payload.update(overrides)
    return payload


class RuntimePort:
    def __init__(self, responder=None, *, epoch=7, org="org-org"):
        self.responder = responder or receipt_payload
        self.epoch = epoch
        self.org = org
        self.commands = []
        self.receipts = {}

    def commit(self, *, dispatch_ref, command):
        if dispatch_ref.execution_epoch != self.epoch:
            raise PermissionError("stale execution epoch")
        if (dispatch_ref.org_id, dispatch_ref.project_id) != (self.org, "dev-project"):
            raise PermissionError("tenant isolation")
        assert not {"tenant", "orgId", "projectId", "dispatchRef"}.intersection(command)
        key = command["idempotencyKey"]
        existing = self.receipts.get(key)
        if existing is not None:
            if existing[0] != command["requestHash"]:
                raise ValueError("idempotency content drift")
            return existing[1]
        self.commands.append(command)
        result = self.responder(command)
        self.receipts[key] = (command["requestHash"], result)
        return result


class WritePort:
    def commit(self, **_kwargs):
        raise AssertionError("N1 write port must not receive N4 commands")


def test_start_creates_incomplete_preparing_receipt_and_replays_exactly() -> None:
    port = RuntimePort()
    request = start_request()
    first = advance_analysis_runtime(port, dispatch_ref=dispatch(), request=request)
    second = advance_analysis_runtime(port, dispatch_ref=dispatch(), request=request)
    assert first == second
    assert first.phase.value == "PREPARING"
    assert first.completed is False
    assert first.run_ref.resource_id == "run-1"
    assert len(port.commands) == 1


def test_same_idempotency_key_with_different_content_is_rejected() -> None:
    port = RuntimePort()
    advance_analysis_runtime(port, dispatch_ref=dispatch(), request=start_request())
    drifted = AnalysisRuntimeRequest(
        occurrence_ref=ref("AutomationOccurrence", "occurrence-2"),
        case_ref=ref("BusinessInvestigationCaseRevision", "case-1"),
        profile_ref=ref("InvestigationProfileRevision", "profile-1"),
        cutoff_at=CUTOFF,
        idempotency_key="occurrence-start-1",
    )
    with pytest.raises(ValueError, match="idempotency content drift"):
        advance_analysis_runtime(port, dispatch_ref=dispatch(), request=drifted)


def test_application_routes_n4_without_using_n1_write_port() -> None:
    port = RuntimePort()
    app = EcommerceGrowthApplication(WritePort(), runtime_port=port)
    assert app.advance_analysis(dispatch_ref=dispatch(), request=start_request()).completed is False
    assert len(port.commands) == 1


def test_waiting_data_requires_exact_requirement_and_checkpoint() -> None:
    def waiting(command):
        return receipt_payload(
            command,
            phase="WAITING_DATA",
            action="WAIT_FOR_DATA",
            requirementRef=exact_payload(ref("DataRequirementRevision", "requirement-1")),
            checkpointRef=exact_payload(ref("CheckpointRevision", "checkpoint-1")),
        )

    result = advance_analysis_runtime(
        RuntimePort(waiting), dispatch_ref=dispatch(), request=start_request()
    )
    assert result.requirement_ref.resource_id == "requirement-1"
    assert result.fulfillment_ref is None


def test_resume_data_binds_same_requirement_fulfillment_and_checkpoint() -> None:
    request = AnalysisRuntimeRequest(
        occurrence_ref=ref("AutomationOccurrence", "occurrence-1"),
        case_ref=ref("BusinessInvestigationCaseRevision", "case-1"),
        profile_ref=ref("InvestigationProfileRevision", "profile-1"),
        cutoff_at=CUTOFF,
        idempotency_key="resume-data-1",
        mode="RESUME_DATA",
        prior_receipt_ref=ref("AnalysisRuntimeReceipt", "waiting-receipt-1"),
        requirement_ref=ref("DataRequirementRevision", "requirement-1"),
        fulfillment_ref=ref("DataFulfillmentReceipt", "fulfillment-1", receipt="fulfillment-receipt-1"),
        checkpoint_ref=ref("CheckpointRevision", "checkpoint-1"),
    )

    def resumed(command):
        return receipt_payload(
            command,
            phase="RUNNING",
            action="CONTINUE",
            requirementRef=command["requirementRef"],
            fulfillmentRef=command["fulfillmentRef"],
            checkpointRef=exact_payload(ref("CheckpointRevision", "checkpoint-2", revision=2)),
        )

    result = advance_analysis_runtime(RuntimePort(resumed), dispatch_ref=dispatch(), request=request)
    assert result.phase.value == "RUNNING"
    assert result.fulfillment_ref == request.fulfillment_ref
    assert result.checkpoint_ref.revision == 2


def test_unknown_only_reconciles_target_receipt_and_never_restarts() -> None:
    target = ref("RuntimeCommandReceipt", "target-command-1", receipt="target-command-1")

    def unknown(command):
        return receipt_payload(
            command,
            phase="UNKNOWN",
            action="RECONCILE_RECEIPT",
            targetReceiptRef=exact_payload(target),
        )

    first_port = RuntimePort(unknown)
    prior = advance_analysis_runtime(first_port, dispatch_ref=dispatch(), request=start_request())
    reconcile = AnalysisRuntimeRequest(
        occurrence_ref=prior.occurrence_ref,
        case_ref=prior.case_ref,
        profile_ref=ref("InvestigationProfileRevision", "profile-1"),
        cutoff_at=CUTOFF,
        idempotency_key="reconcile-1",
        mode="RECONCILE_UNKNOWN",
        prior_receipt_ref=prior.receipt_ref,
        checkpoint_ref=None,
    )

    def reconciling(command):
        assert command["operation"] == "runtime.analysis.reconcile_unknown"
        assert command["priorReceiptRef"] == exact_payload(prior.receipt_ref)
        return receipt_payload(
            command,
            phase="RECONCILING",
            action="RECONCILE_RECEIPT",
            targetReceiptRef=exact_payload(target),
        )

    second_port = RuntimePort(reconciling)
    result = advance_analysis_runtime(second_port, dispatch_ref=dispatch(), request=reconcile)
    assert result.target_receipt_ref == target
    assert len(first_port.commands) == len(second_port.commands) == 1


@pytest.mark.parametrize(
    "responder,match",
    [
        (lambda c: receipt_payload(c, completed=True), "cannot claim analysis completion"),
        (
            lambda c: receipt_payload(c, planRef=exact_payload(ref("TaskRun", "wrong"))),
            "reference type drifted",
        ),
        (
            lambda c: receipt_payload(c, occurrenceRef=exact_payload(ref("AutomationOccurrence", "other"))),
            "input lineage drifted",
        ),
        (
            lambda c: receipt_payload(c, cutoffAt="2026-09-08T01:00:00+00:00"),
            "cutoff drifted",
        ),
        (
            lambda c: receipt_payload(c, phase="WAITING_DATA", action="WAIT_FOR_DATA"),
            "WAITING_DATA runtime lineage is incomplete",
        ),
    ],
)
def test_runtime_response_drift_fails_closed(responder, match) -> None:
    with pytest.raises(ValueError, match=match):
        advance_analysis_runtime(RuntimePort(responder), dispatch_ref=dispatch(), request=start_request())


def test_stale_epoch_cross_tenant_and_wrong_operation_are_rejected() -> None:
    with pytest.raises(PermissionError, match="stale execution epoch"):
        advance_analysis_runtime(RuntimePort(), dispatch_ref=dispatch(epoch=6), request=start_request())
    with pytest.raises(PermissionError, match="tenant isolation"):
        advance_analysis_runtime(RuntimePort(), dispatch_ref=dispatch(org="dev-org"), request=start_request())
    with pytest.raises(PermissionError, match="does not authorize"):
        advance_analysis_runtime(
            RuntimePort(), dispatch_ref=dispatch(operation="ecommerce_growth_case_put"), request=start_request()
        )


def test_resume_and_reconcile_cannot_regress_to_preparing() -> None:
    resume = AnalysisRuntimeRequest(
        occurrence_ref=ref("AutomationOccurrence", "occurrence-1"),
        case_ref=ref("BusinessInvestigationCaseRevision", "case-1"),
        profile_ref=ref("InvestigationProfileRevision", "profile-1"),
        cutoff_at=CUTOFF,
        idempotency_key="resume-regression-1",
        mode="RESUME_DATA",
        prior_receipt_ref=ref("AnalysisRuntimeReceipt", "waiting-receipt-1"),
        requirement_ref=ref("DataRequirementRevision", "requirement-1"),
        fulfillment_ref=ref("DataFulfillmentReceipt", "fulfillment-1"),
        checkpoint_ref=ref("CheckpointRevision", "checkpoint-1"),
    )
    with pytest.raises(ValueError, match="does not match recovery mode"):
        advance_analysis_runtime(RuntimePort(), dispatch_ref=dispatch(), request=resume)


def test_package_runtime_has_no_platform_or_side_effect_imports() -> None:
    package = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analysis_runtime.py"
    source = package.read_text(encoding="utf-8")
    for forbidden in ("aos_api", "psycopg", "requests", "httpx", "subprocess", "socket"):
        assert forbidden not in source
