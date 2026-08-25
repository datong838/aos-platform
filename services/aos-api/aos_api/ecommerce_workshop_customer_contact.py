"""W6-08 customer contact governance without contact resolution or dispatch."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.ecommerce_workshop_customer_lifecycle import (
    CUSTOMER_LOGIC_ID,
    CUSTOMER_SKILL_IDS,
    ConsentDecision,
    CustomerBatchDisposition,
    CustomerDialogueBatchRevision,
    canonical_hash,
)
from aos_api.tenant_scope import TenantScope


CUSTOMER_CONTACT_SCHEMA_VERSION = "aos.ecommerce-workshop.customer-contact-governance/v1"


class CustomerContactBlocked(RuntimeError):
    code = "CUSTOMER_CONTACT_BLOCKED"


class CustomerContactConflict(CustomerContactBlocked):
    code = "CUSTOMER_CONTACT_CONFLICT"


class CustomerContactItemState(StrEnum):
    RESERVED = "reserved"
    SKIPPED_WITHDRAWN = "skipped_withdrawn"
    CANCELLED = "cancelled"
    ACCEPTED = "accepted"
    APPLIED = "applied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"


class CreateCustomerFrequencyPolicyRequest(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    channel: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=160)
    timezone: str = Field(min_length=1, max_length=80)
    quiet_hours_start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    rolling_window_hours: int = Field(ge=1, le=24 * 365)
    maximum_contacts: int = Field(ge=1, le=1000)
    unknown_behavior: str = Field(default="block", pattern=r"^block$")


class CustomerFrequencyPolicyRevision(CreateCustomerFrequencyPolicyRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class RecordCustomerConsentWithdrawalRequest(AipContractModel):
    customer_ref: CustomerExactRef
    consent_policy_ref: CustomerExactRef
    purpose: str = Field(min_length=1, max_length=160)
    channel: str = Field(min_length=1, max_length=80)
    sequence: int = Field(ge=1)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _refs(self) -> "RecordCustomerConsentWithdrawalRequest":
        if self.customer_ref.resource_type != "CustomerLiteProjectionRevision":
            raise ValueError("withdrawal customerRef must remain CustomerLite")
        if self.consent_policy_ref.resource_type != "CustomerConsentPolicyRevision":
            raise ValueError("withdrawal consentPolicyRef drifted")
        return self


class CustomerConsentWithdrawalObservation(RecordCustomerConsentWithdrawalRequest):
    tenant: TenantContext
    observation_id: str
    revision: int = 1
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class StartCustomerDialogueItem(AipContractModel):
    item_key: str = Field(min_length=1, max_length=200)
    item_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    customer_ref: CustomerExactRef

    @model_validator(mode="after")
    def _customer(self) -> "StartCustomerDialogueItem":
        if self.customer_ref.resource_type != "CustomerLiteProjectionRevision":
            raise ValueError("start item accepts only CustomerLiteProjectionRevision")
        return self


class StartCustomerDialogueBatchRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent_policy_ref: CustomerExactRef
    frequency_policy_ref: CustomerExactRef
    action_type_ref: CustomerExactRef
    impact_preview_ref: CustomerExactRef
    approval_policy_ref: CustomerExactRef
    account_binding_ref: CustomerExactRef
    adapter_capability_ref: CustomerExactRef
    content_ref: CustomerExactRef
    start_sequence: int = Field(ge=1)
    items: list[StartCustomerDialogueItem] = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _refs(self) -> "StartCustomerDialogueBatchRequest":
        expected = (
            (self.consent_policy_ref, "CustomerConsentPolicyRevision"),
            (self.frequency_policy_ref, "FrequencyPolicyRevision"),
            (self.action_type_ref, "ActionTypeRevision"),
            (self.impact_preview_ref, "ImpactPreviewRevision"),
            (self.approval_policy_ref, "ApprovalPolicyRevision"),
            (self.account_binding_ref, "AccountBindingRevision"),
            (self.adapter_capability_ref, "AdapterCapabilityRevision"),
            (self.content_ref, "ArtifactRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("customer start exact refs drifted")
        keys = [item.item_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("customer start item keys must be unique")
        return self


class CustomerFrequencyReservationRevision(AipContractModel):
    tenant: TenantContext
    reservation_id: str
    batch_ref: CustomerExactRef
    item_key: str = Field(min_length=1, max_length=200)
    customer_ref: CustomerExactRef
    frequency_policy_ref: CustomerExactRef
    sequence: int = Field(ge=1)
    status: str = Field(pattern=r"^held$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class CustomerContactExecutionPermitRevision(AipContractModel):
    permit_id: str
    customer_ref: CustomerExactRef
    sequence: int = Field(ge=1)
    status: str = Field(pattern=r"^not_redeemable$")
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_contact_count: int = Field(default=0, ge=0, le=0)


class CustomerDispatchAttemptRevision(AipContractModel):
    attempt_id: str
    customer_ref: CustomerExactRef
    sequence: int = Field(ge=1)
    status: str = Field(pattern=r"^prepared$")
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    outbox_intent_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_call_count: int = Field(default=0, ge=0, le=0)


class CustomerContactItemBinding(AipContractModel):
    item_key: str
    item_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    customer_ref: CustomerExactRef
    state: CustomerContactItemState
    withdrawal_sequence: int | None = Field(default=None, ge=1)
    reservation: CustomerFrequencyReservationRevision | None = None
    permit: CustomerContactExecutionPermitRevision | None = None
    attempt: CustomerDispatchAttemptRevision | None = None
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_receipt_ref: CustomerExactRef | None = None
    resolved_state: CustomerContactItemState | None = None


class CustomerContactLedger(AipContractModel):
    frozen_eligible: int = Field(ge=0)
    reserved: int = Field(ge=0)
    skipped_withdrawn: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    accepted: int = Field(ge=0)
    applied: int = Field(ge=0)
    failed: int = Field(ge=0)
    unknown: int = Field(ge=0)
    disputed: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserved(self) -> "CustomerContactLedger":
        total = self.reserved + self.skipped_withdrawn + self.cancelled + self.accepted + self.applied + self.failed + self.unknown + self.disputed
        if self.frozen_eligible != total:
            raise ValueError("customer contact ledger must conserve frozen eligible items")
        return self


class CustomerBatchStartDecisionRevision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    revision: int = 1
    lifecycle: str = Field(pattern=r"^governance_prepared$")
    batch_ref: CustomerExactRef
    start_sequence: int = Field(ge=1)
    exact_refs: dict[str, CustomerExactRef]
    items: list[CustomerContactItemBinding]
    ledger: CustomerContactLedger
    operational_blockers: list[str]
    contact_resolution_count: int = Field(default=0, ge=0, le=0)
    provider_call_count: int = Field(default=0, ge=0, le=0)
    send_count: int = Field(default=0, ge=0, le=0)
    external_effect_count: int = Field(default=0, ge=0, le=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_by: str
    started_at: datetime


class RecordCustomerDispatchObservationRequest(AipContractModel):
    start_decision_ref: CustomerExactRef
    item_key: str = Field(min_length=1, max_length=200)
    action_receipt_ref: CustomerExactRef
    state: CustomerContactItemState
    resolved_state: CustomerContactItemState | None = None
    manual_case_ref: CustomerExactRef | None = None
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _refs(self) -> "RecordCustomerDispatchObservationRequest":
        if self.start_decision_ref.resource_type != "CustomerBatchStartDecisionRevision":
            raise ValueError("startDecisionRef drifted")
        if self.action_receipt_ref.resource_type != "ActionReceipt":
            raise ValueError("actionReceiptRef drifted")
        if self.manual_case_ref and self.manual_case_ref.resource_type != "ManualReconcileCase":
            raise ValueError("manualCaseRef drifted")
        if self.state in {CustomerContactItemState.RESERVED, CustomerContactItemState.SKIPPED_WITHDRAWN}:
            raise ValueError("dispatch observation cannot manufacture pre-dispatch state")
        if self.state is CustomerContactItemState.UNKNOWN and self.resolved_state is not None:
            raise ValueError("unknown observation cannot self-resolve")
        if self.resolved_state is not None:
            if self.state is not CustomerContactItemState.DISPUTED or self.resolved_state in {CustomerContactItemState.RESERVED, CustomerContactItemState.SKIPPED_WITHDRAWN, CustomerContactItemState.UNKNOWN, CustomerContactItemState.DISPUTED} or self.manual_case_ref is None:
                raise ValueError("resolvedState requires disputed observation and exact manual case")
        return self


class CustomerDispatchObservation(RecordCustomerDispatchObservationRequest):
    tenant: TenantContext
    observation_id: str
    revision: int = 1
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CustomerContactContributionView(AipContractModel):
    schema_version: str = CUSTOMER_CONTACT_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    atomic_skill_ids: list[str] = Field(default_factory=lambda: list(CUSTOMER_SKILL_IDS))
    logic_id: str = CUSTOMER_LOGIC_ID
    primary_colleague: str = "私域管家"
    collaborator_colleagues: list[str] = Field(default_factory=lambda: ["内容官", "客服专员", "导购顾问", "数据参谋"])
    latest_start: CustomerBatchStartDecisionRevision | None
    ledger: CustomerContactLedger
    frequency_policy_count: int = Field(ge=0)
    withdrawal_count: int = Field(ge=0)
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: [
        "CREATE_CUSTOMER_FREQUENCY_POLICY", "RECORD_CUSTOMER_CONSENT_WITHDRAWAL",
        "START_CUSTOMER_DIALOGUE_BATCH_GOVERNANCE", "RECORD_CUSTOMER_DISPATCH_OBSERVATION",
    ])
    permit_redemption_allowed: bool = False
    contact_resolution_allowed: bool = False
    provider_dispatch_allowed: bool = False
    send_allowed: bool = False
    external_effects_allowed: bool = False


def _ledger(items: list[CustomerContactItemBinding]) -> CustomerContactLedger:
    counts = {state.value: 0 for state in CustomerContactItemState}
    for item in items:
        counts[(item.resolved_state or item.state).value] += 1
    return CustomerContactLedger(frozenEligible=len(items), **counts)


class EcommerceWorkshopCustomerContactService:
    def __init__(self, store: Any, batch_store: Any) -> None:
        self.store = store
        self.batch_store = batch_store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _batch_ref(batch: CustomerDialogueBatchRevision) -> CustomerExactRef:
        return CustomerExactRef(resourceType="CustomerDialogueBatchRevision", resourceId=batch.batch_id, revision=batch.revision, contentHash=f"sha256:{batch.content_hash}", receiptId=f"receipt-{batch.batch_id}")

    def create_frequency_policy(self, scope: TenantScope, request: CreateCustomerFrequencyPolicyRequest, actor: str, *, now: datetime | None = None) -> CustomerFrequencyPolicyRevision:
        at = now or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        item = CustomerFrequencyPolicyRevision(tenant=self._tenant(scope), **payload, contentHash=canonical_hash(payload), createdBy=actor, createdAt=at)
        return self.store.append_frequency_policy(scope, item)

    def record_withdrawal(self, scope: TenantScope, request: RecordCustomerConsentWithdrawalRequest) -> CustomerConsentWithdrawalObservation:
        self.store.require_consent_policy(scope, request.consent_policy_ref)
        payload = request.model_dump(mode="json", by_alias=True)
        item = CustomerConsentWithdrawalObservation(
            tenant=self._tenant(scope), observationId=f"customer-withdrawal-{canonical_hash(payload)[:24]}",
            **payload, contentHash=canonical_hash(payload),
        )
        return self.store.append_withdrawal(scope, item)

    def start_batch(self, scope: TenantScope, batch_id: str, request: StartCustomerDialogueBatchRequest, actor: str, *, now: datetime | None = None) -> CustomerBatchStartDecisionRevision:
        at = now or datetime.now(UTC)
        batch = self.batch_store.latest_batch(scope, batch_id)
        if batch.lifecycle != "frozen":
            raise CustomerContactBlocked("CUSTOMER_DIALOGUE_BATCH_NOT_FROZEN")
        if batch.version != request.expected_version or batch.content_hash != request.expected_content_hash:
            raise CustomerContactConflict("CUSTOMER_DIALOGUE_BATCH_EXPECTED_VERSION_OR_HASH_DRIFTED")
        if batch.consent_policy_ref != request.consent_policy_ref or batch.frequency_policy_ref != request.frequency_policy_ref:
            raise CustomerContactBlocked("CUSTOMER_START_BATCH_POLICY_REF_DRIFTED")
        eligible = [item for item in batch.items if item.disposition is CustomerBatchDisposition.ELIGIBLE]
        expected = {
            (item.item_key, batch.item_hashes[index], canonical_hash(item.customer_ref.model_dump(mode="json", by_alias=True)))
            for index, item in enumerate(batch.items)
            if item.disposition is CustomerBatchDisposition.ELIGIBLE
        }
        actual = {
            (item.item_key, item.item_hash, canonical_hash(item.customer_ref.model_dump(mode="json", by_alias=True)))
            for item in request.items
        }
        if actual != expected:
            raise CustomerContactBlocked("CUSTOMER_START_ITEM_COVERAGE_OR_HASH_DRIFTED")
        self.store.require_start_authorities(scope, request)
        exact_refs = {
            "consentPolicy": request.consent_policy_ref, "frequencyPolicy": request.frequency_policy_ref,
            "actionType": request.action_type_ref, "impactPreview": request.impact_preview_ref,
            "approvalPolicy": request.approval_policy_ref, "accountBinding": request.account_binding_ref,
            "adapterCapability": request.adapter_capability_ref, "content": request.content_ref,
        }
        bindings: list[CustomerContactItemBinding] = []
        for start_item in sorted(request.items, key=lambda value: value.item_key):
            withdrawal = self.store.latest_withdrawal_or_none(scope, start_item.customer_ref, request.consent_policy_ref)
            withdrawn_first = withdrawal is not None and withdrawal.sequence <= request.start_sequence
            base = {"batchRef": self._batch_ref(batch), "item": start_item, "exactRefs": exact_refs, "startSequence": request.start_sequence}
            binding_hash = canonical_hash(base)
            if withdrawn_first:
                bindings.append(CustomerContactItemBinding(
                    **start_item.model_dump(mode="json", by_alias=True), state=CustomerContactItemState.SKIPPED_WITHDRAWN,
                    withdrawalSequence=withdrawal.sequence, bindingHash=binding_hash,
                ))
                continue
            reservation = CustomerFrequencyReservationRevision(
                tenant=self._tenant(scope), reservationId=f"customer-frequency-{binding_hash[:24]}",
                batchRef=self._batch_ref(batch), itemKey=start_item.item_key, customerRef=start_item.customer_ref,
                frequencyPolicyRef=request.frequency_policy_ref, sequence=request.start_sequence, status="held",
                contentHash=canonical_hash({"bindingHash": binding_hash, "kind": "frequency"}), createdAt=at,
            )
            reservation = self.store.reserve_frequency(scope, reservation)
            permit = CustomerContactExecutionPermitRevision(
                permitId=f"customer-permit-{binding_hash[:24]}", customerRef=start_item.customer_ref,
                sequence=request.start_sequence, status="not_redeemable", bindingHash=binding_hash,
            )
            attempt = CustomerDispatchAttemptRevision(
                attemptId=f"customer-attempt-{binding_hash[:24]}", customerRef=start_item.customer_ref,
                sequence=request.start_sequence, status="prepared", bindingHash=binding_hash,
                outboxIntentHash=canonical_hash({"bindingHash": binding_hash, "kind": "outbox-intent"}),
            )
            bindings.append(CustomerContactItemBinding(
                **start_item.model_dump(mode="json", by_alias=True), state=CustomerContactItemState.RESERVED,
                reservation=reservation, permit=permit, attempt=attempt, bindingHash=binding_hash,
            ))
        payload = {"batchRef": self._batch_ref(batch), "startSequence": request.start_sequence, "exactRefs": exact_refs, "items": bindings, "reason": request.reason}
        content_hash = canonical_hash(payload)
        existing = self.store.latest_start_or_none(scope, batch_id)
        if existing is not None:
            if existing.content_hash == content_hash:
                return existing
            raise CustomerContactConflict("CUSTOMER_BATCH_START_IDEMPOTENCY_CONFLICT")
        item = CustomerBatchStartDecisionRevision(
            tenant=self._tenant(scope), decisionId=f"customer-start-{canonical_hash([*scope.key, batch_id])[:24]}",
            lifecycle="governance_prepared", batchRef=self._batch_ref(batch), startSequence=request.start_sequence,
            exactRefs=exact_refs, items=bindings, ledger=_ledger(bindings),
            operationalBlockers=["CUSTOMER_CONTACT_PERMIT_REDEMPTION_NOT_AUTHORIZED", "CUSTOMER_PROVIDER_DISPATCH_NOT_AUTHORIZED", "CUSTOMER_EXTERNAL_EFFECT_NOT_AUTHORIZED"],
            contentHash=content_hash, startedBy=actor, startedAt=at,
        )
        return self.store.append_start(scope, batch_id, item)

    def record_dispatch_observation(self, scope: TenantScope, request: RecordCustomerDispatchObservationRequest) -> CustomerDispatchObservation:
        start = self.store.require_start(scope, request.start_decision_ref)
        binding = next((item for item in start.items if item.item_key == request.item_key), None)
        if binding is None or binding.state is CustomerContactItemState.SKIPPED_WITHDRAWN:
            raise CustomerContactBlocked("CUSTOMER_CONTACT_ITEM_NOT_OBSERVABLE")
        self.store.require_action_receipt(scope, request.action_receipt_ref, binding.binding_hash)
        payload = request.model_dump(mode="json", by_alias=True)
        item = CustomerDispatchObservation(
            tenant=self._tenant(scope), observationId=f"customer-dispatch-observation-{canonical_hash(payload)[:24]}",
            **payload, contentHash=canonical_hash(payload),
        )
        return self.store.append_dispatch_observation(scope, item)

    def contribution_view(self, scope: TenantScope, *, now: datetime | None = None) -> CustomerContactContributionView:
        at = now or datetime.now(UTC)
        try:
            latest = self.store.latest_start_for_tenant_or_none(scope)
            counts = self.store.authority_counts(scope)
            observations = [] if latest is None else self.store.list_dispatch_observations(scope, latest.decision_id)
            if latest is not None and observations:
                by_key = {item.item_key: item.model_copy(deep=True) for item in latest.items}
                for observation in observations:
                    item = by_key.get(observation.item_key)
                    if item is not None:
                        item.state = observation.state
                        item.resolved_state = observation.resolved_state
                        item.action_receipt_ref = observation.action_receipt_ref
                latest = latest.model_copy(update={"items": list(by_key.values()), "ledger": _ledger(list(by_key.values()))})
            blockers = ["CUSTOMER_CONTACT_GOVERNANCE_NOT_PREPARED"] if latest is None else list(latest.operational_blockers)
        except CustomerContactBlocked as exc:
            latest = None
            counts = {"frequency_policy": 0, "withdrawal": 0}
            blockers = [str(exc)]
        ledger = CustomerContactLedger(frozenEligible=0, reserved=0, skippedWithdrawn=0, cancelled=0, accepted=0, applied=0, failed=0, unknown=0, disputed=0) if latest is None else latest.ledger
        return CustomerContactContributionView(
            tenant=self._tenant(scope), evaluatedAt=at, latestStart=latest, ledger=ledger,
            frequencyPolicyCount=counts["frequency_policy"], withdrawalCount=counts["withdrawal"], blockers=blockers,
        )


__all__ = [name for name in globals() if name.startswith("Customer") or name.startswith("CreateCustomer") or name.startswith("RecordCustomer") or name.startswith("StartCustomer") or name == "EcommerceWorkshopCustomerContactService"]
