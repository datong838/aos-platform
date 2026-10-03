"""One BI Plan attempt followed by original Receipt readback; never auto-resend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from aos_api.aip_bi_plan_issuer_auth import authenticate_bi_issuer_request
from aos_api.aip_bi_plan_issuer_contracts import (
    BIIssuerPrepareCommand, BIIssuerRebindCommand,
)
from aos_api.aip_network_issuer_attempt import (
    AttemptAlreadyRecorded, AttemptBlocked, AttemptConflict, AttemptReceipt,
    _reserve_attempt_receipt,
)
from aos_api.aip_production_contract_store import (
    SignedBIPlanReceiptReadback, SignedBIPlanRebindReceiptReadback, canonical_hash,
)
from aos_api.tenant_scope import TenantScope


BIReceipt = SignedBIPlanReceiptReadback | SignedBIPlanRebindReceiptReadback


@dataclass(frozen=True)
class BIIssuerOutcome:
    status: Literal["observed", "unresolved", "conflict"]
    receipt: BIReceipt | None = None


def _matches_prepare(command: BIIssuerPrepareCommand, principal, receipt) -> bool:
    if type(receipt) is not SignedBIPlanReceiptReadback:
        return False
    binding = receipt.installation_binding
    return (receipt.plan_revision_verified is True
            and receipt.current_admission_verified is False
            and receipt.installation_binding_verified is True
            and binding is not None
            and receipt.result_ref.resource_type == "ResponsibilityPlanRevision"
            and binding.installation_id == command.installation_id
            and binding.installation_etag == command.expected_etag_version
            and binding.actor == principal.subject)


def _matches_rebind(command: BIIssuerRebindCommand, principal,
                    receipt, original) -> bool:
    if (type(receipt) is not SignedBIPlanRebindReceiptReadback
            or type(original) is not SignedBIPlanReceiptReadback):
        return False
    binding, prior = receipt.rebind_binding, original.installation_binding
    return (receipt.original_preparation_verified is True
            and receipt.plan_revision_verified is True
            and receipt.current_admission_verified is False
            and original.plan_revision_verified is True
            and original.installation_binding_verified is True
            and prior is not None
            and receipt.result_ref.resource_type == "ResponsibilityPlanRevision"
            and receipt.result_ref.resource_id == command.plan_id
            and receipt.result_ref.revision == command.expected_plan_version + 1
            and original.result_ref.resource_id == command.plan_id
            and original.receipt_id == binding.prepare_receipt_id
            and prior.installation_id == binding.installation_id == command.installation_id
            and prior.installation_etag < binding.installation_etag == command.expected_etag_version
            and prior.actor == binding.actor == principal.subject)


def _readback(command, scope, principal, prepare_reader, rebind_reader) -> BIIssuerOutcome:
    try:
        if type(command) is BIIssuerPrepareCommand:
            receipt = prepare_reader.read(
                scope, principal=principal, idempotency_key=command.idempotency_key)
            matched = _matches_prepare(command, principal, receipt)
        else:
            receipt = rebind_reader.read(
                scope, principal=principal, idempotency_key=command.idempotency_key)
            original = prepare_reader.read(
                scope, principal=principal, idempotency_key=command.prepare_key)
            matched = _matches_rebind(command, principal, receipt, original)
    except Exception:
        return BIIssuerOutcome("unresolved")
    if not matched:
        return BIIssuerOutcome("conflict")
    return BIIssuerOutcome("observed", receipt)


def dispatch_bi_issuer_command(
    command: BIIssuerPrepareCommand | BIIssuerRebindCommand, *,
    attempt_directory: str | Path,
    prepare_service, rebind_service, prepare_receipt_reader, rebind_receipt_reader,
) -> BIIssuerOutcome:
    """A future isolated process supplies all DB dependencies; no defaults here."""
    if (type(command) not in (BIIssuerPrepareCommand, BIIssuerRebindCommand)
            or not callable(getattr(prepare_service, "prepare", None))
            or not callable(getattr(rebind_service, "rebind", None))
            or not callable(getattr(prepare_receipt_reader, "read", None))
            or not callable(getattr(rebind_receipt_reader, "read", None))):
        raise ValueError("BI_ISSUER_EXACT_DEPENDENCIES_REQUIRED")
    principal = authenticate_bi_issuer_request(command)
    scope = TenantScope(command.org_id, command.project_id)
    operation = "prepare" if type(command) is BIIssuerPrepareCommand else "rebind"
    digest = canonical_hash({
        "operation": operation, "actor": principal.subject,
        "command": command.model_dump(mode="json", by_alias=True,
                                      exclude={"bearer_token"}),
    })
    marker = AttemptReceipt(command.org_id, command.project_id,
                            command.installation_id, command.idempotency_key,
                            digest, principal.subject)
    try:
        _reserve_attempt_receipt(attempt_directory, marker,
                                 namespace=f"bi-plan-{operation}/v1")
    except AttemptAlreadyRecorded:
        return _readback(command, scope, principal,
                         prepare_receipt_reader, rebind_receipt_reader)
    except AttemptConflict:
        return BIIssuerOutcome("conflict")
    except AttemptBlocked:
        return BIIssuerOutcome("unresolved")
    try:
        if operation == "prepare":
            prepare_service.prepare(
                scope, installation_id=command.installation_id,
                expected_etag_version=command.expected_etag_version,
                principal=principal, idempotency_key=command.idempotency_key)
        else:
            rebind_service.rebind(
                scope, installation_id=command.installation_id,
                plan_id=command.plan_id, prepare_key=command.prepare_key,
                expected_etag_version=command.expected_etag_version,
                expected_plan_version=command.expected_plan_version,
                principal=principal, idempotency_key=command.idempotency_key)
    except Exception:
        # The transaction may have committed before transport failure.
        pass
    return _readback(command, scope, principal,
                     prepare_receipt_reader, rebind_receipt_reader)
