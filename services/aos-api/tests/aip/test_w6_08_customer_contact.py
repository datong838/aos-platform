from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_customer_contact import (
    CreateCustomerFrequencyPolicyRequest,
    CustomerContactBlocked,
    CustomerContactConflict,
    CustomerContactItemState,
    EcommerceWorkshopCustomerContactService,
    RecordCustomerConsentWithdrawalRequest,
    RecordCustomerDispatchObservationRequest,
    StartCustomerDialogueBatchRequest,
)
from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.ecommerce_workshop_customer_lifecycle import (
    ConsentDecision,
    CustomerBatchDisposition,
    CustomerDialogueBatchLedger,
    CustomerDialogueBatchRevision,
    PrepareCustomerDialogueBatchItem,
    canonical_hash,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")


def ref(kind: str, identity: str, digest: str = "a", revision: int = 1) -> CustomerExactRef:
    return CustomerExactRef(resourceType=kind, resourceId=identity, revision=revision, contentHash=f"sha256:{digest * 64}", receiptId=f"receipt-{identity}")


def full_ref(kind: str, identity: str, content_hash: str, revision: int = 1) -> CustomerExactRef:
    return CustomerExactRef(resourceType=kind, resourceId=identity, revision=revision, contentHash=f"sha256:{content_hash}", receiptId=f"receipt-{identity}")


def frozen_batch() -> CustomerDialogueBatchRevision:
    item = PrepareCustomerDialogueBatchItem(
        itemKey="item-1", customerRef=ref("CustomerLiteProjectionRevision", "customer-1"),
        disposition=CustomerBatchDisposition.ELIGIBLE, consentDecision=ConsentDecision.GRANTED,
        retentionActive=True, kAnonymitySatisfied=True, eligibilityEvidenceRefs=[ref("ConsentRevision", "consent-1")],
    )
    item_hash = canonical_hash(item.model_dump(mode="json", by_alias=True))
    return CustomerDialogueBatchRevision(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id), batchId="batch-1", revision=2, version=2,
        lifecycle="frozen", segmentRef=ref("CustomerSegmentRevision", "segment-1"), journeyRef=ref("CustomerJourneyRevision", "journey-1"),
        dialogueRef=ref("CustomerDialogueStrategyRevision", "dialogue-1"), consentPolicyRef=ref("CustomerConsentPolicyRevision", "consent-policy"),
        frequencyPolicyRef=ref("FrequencyPolicyRevision", "frequency-policy"), channelCapabilityRef=ref("CapabilityBindingRevision", "channel-capability"),
        items=[item], itemHashes=[item_hash], ledger=CustomerDialogueBatchLedger(input=1, eligible=1, excluded=0, needsReview=0, unknown=0, deduplicated=0),
        bindingHash="b" * 64, priorContentHash="c" * 64, contentHash="d" * 64, createdBy="reviewer", createdAt=NOW,
    )


class BatchStore:
    def __init__(self) -> None: self.batch = frozen_batch()
    def latest_batch(self, scope, batch_id):
        if scope != SCOPE or batch_id != self.batch.batch_id: raise CustomerContactBlocked("CUSTOMER_DIALOGUE_BATCH_NOT_FOUND")
        return self.batch


class MemoryStore:
    def __init__(self) -> None:
        self.policies = []; self.reservations = {}; self.withdrawals = []; self.starts = {}; self.observations = []; self.receipts = {}
    def append_frequency_policy(self, scope, item): assert scope == SCOPE; self.policies.append(item); return item
    def require_consent_policy(self, scope, exact): assert scope == SCOPE and exact.resource_type == "CustomerConsentPolicyRevision"
    def append_withdrawal(self, scope, item): assert scope == SCOPE; self.withdrawals.append(item); return item
    def latest_withdrawal_or_none(self, scope, customer, consent): return next((item for item in reversed(self.withdrawals) if scope == SCOPE and item.customer_ref == customer and item.consent_policy_ref == consent), None)
    def require_start_authorities(self, scope, request): assert scope == SCOPE and request.action_type_ref.resource_id == "ecommerce.customer.dialogue-send"
    def reserve_frequency(self, scope, item):
        assert scope == SCOPE
        existing = self.reservations.get(item.reservation_id)
        if existing is not None:
            if existing.content_hash != item.content_hash: raise CustomerContactBlocked("CUSTOMER_FREQUENCY_RESERVATION_IDEMPOTENCY_CONFLICT")
            return existing
        policy = next((value for value in reversed(self.policies) if value.policy_id == item.frequency_policy_ref.resource_id), None)
        limit = policy.maximum_contacts if policy is not None else 1000
        held = sum(1 for value in self.reservations.values() if value.customer_ref == item.customer_ref and value.frequency_policy_ref == item.frequency_policy_ref)
        if held >= limit: raise CustomerContactBlocked("CUSTOMER_FREQUENCY_LIMIT_EXCEEDED")
        self.reservations[item.reservation_id] = item
        return item
    def latest_start_or_none(self, scope, batch_id): return self.starts.get((*scope.key, batch_id))
    def append_start(self, scope, batch_id, item): self.starts[(*scope.key, batch_id)] = item; return item
    def latest_start_for_tenant_or_none(self, scope): return next((item for key, item in self.starts.items() if key[:2] == scope.key), None)
    def require_start(self, scope, exact):
        item = next((item for key, item in self.starts.items() if key[:2] == scope.key and item.decision_id == exact.resource_id), None)
        if item is None or f"sha256:{item.content_hash}" != exact.content_hash: raise CustomerContactBlocked("CUSTOMER_START_DECISION_MISSING_OR_DRIFTED")
        return item
    def require_action_receipt(self, scope, exact, binding_hash):
        if self.receipts.get((*scope.key, exact.resource_id)) != (exact.content_hash, binding_hash): raise CustomerContactBlocked("CUSTOMER_ACTION_RECEIPT_MISSING_OR_DRIFTED")
    def append_dispatch_observation(self, scope, item): assert scope == SCOPE; self.observations.append(item); return item
    def list_dispatch_observations(self, scope, decision_id): return [item for item in self.observations if scope == SCOPE and item.start_decision_ref.resource_id == decision_id]
    def authority_counts(self, scope): return {"frequency_policy": len(self.policies) if scope == SCOPE else 0, "withdrawal": len(self.withdrawals) if scope == SCOPE else 0}


def start_request(batch: CustomerDialogueBatchRevision) -> StartCustomerDialogueBatchRequest:
    return StartCustomerDialogueBatchRequest(
        expectedVersion=batch.version, expectedContentHash=batch.content_hash, consentPolicyRef=batch.consent_policy_ref,
        frequencyPolicyRef=batch.frequency_policy_ref, actionTypeRef=ref("ActionTypeRevision", "ecommerce.customer.dialogue-send"),
        impactPreviewRef=ref("ImpactPreviewRevision", "impact-1"), approvalPolicyRef=ref("ApprovalPolicyRevision", "approval-1"),
        accountBindingRef=ref("AccountBindingRevision", "account-1"), adapterCapabilityRef=ref("AdapterCapabilityRevision", "adapter-1"),
        contentRef=ref("ArtifactRevision", "content-1"), startSequence=10,
        items=[{"itemKey": "item-1", "itemHash": batch.item_hashes[0], "customerRef": batch.items[0].customer_ref}], reason="用户显式进入触达治理链",
    )


def service_fixture():
    store = MemoryStore(); batches = BatchStore()
    return EcommerceWorkshopCustomerContactService(store, batches), store, batches.batch


def test_start_builds_frequency_reservation_nonredeemable_permit_and_durable_attempt_without_effect():
    service, store, batch = service_fixture()
    policy = service.create_frequency_policy(SCOPE, CreateCustomerFrequencyPolicyRequest(
        policyId="frequency-policy", revision=1, channel="wecom", purpose="retention", timezone="Asia/Shanghai",
        quietHoursStart="22:00", quietHoursEnd="08:00", rollingWindowHours=168, maximumContacts=2,
    ), "operator", now=NOW)
    assert policy.maximum_contacts == 2
    started = service.start_batch(SCOPE, batch.batch_id, start_request(batch), "operator", now=NOW)
    binding = started.items[0]
    assert binding.state is CustomerContactItemState.RESERVED
    assert binding.reservation and binding.reservation.status == "held"
    assert binding.permit and binding.permit.status == "not_redeemable" and binding.permit.raw_contact_count == 0
    assert binding.attempt and binding.attempt.status == "prepared" and binding.attempt.provider_call_count == 0
    assert started.contact_resolution_count == started.provider_call_count == started.send_count == started.external_effect_count == 0
    assert service.start_batch(SCOPE, batch.batch_id, start_request(batch), "operator", now=NOW) == started
    assert store.observations == []


def test_withdrawal_sequence_before_start_skips_without_reservation_or_permit():
    service, _store, batch = service_fixture()
    service.record_withdrawal(SCOPE, RecordCustomerConsentWithdrawalRequest(
        customerRef=batch.items[0].customer_ref, consentPolicyRef=batch.consent_policy_ref,
        purpose="retention", channel="wecom", sequence=9, observedAt=NOW,
    ))
    started = service.start_batch(SCOPE, batch.batch_id, start_request(batch), "operator", now=NOW)
    item = started.items[0]
    assert item.state is CustomerContactItemState.SKIPPED_WITHDRAWN and item.withdrawal_sequence == 9
    assert item.reservation is item.permit is item.attempt is None
    assert started.ledger.skipped_withdrawn == 1 and started.ledger.reserved == 0


def test_start_fails_closed_on_cas_item_hash_and_cross_tenant():
    service, _store, batch = service_fixture()
    with pytest.raises(CustomerContactConflict, match="EXPECTED_VERSION_OR_HASH_DRIFTED"):
        service.start_batch(SCOPE, batch.batch_id, start_request(batch).model_copy(update={"expected_version": 99}), "operator", now=NOW)
    bad_item = start_request(batch).items[0].model_copy(update={"item_hash": "e" * 64})
    with pytest.raises(CustomerContactBlocked, match="ITEM_COVERAGE_OR_HASH_DRIFTED"):
        service.start_batch(SCOPE, batch.batch_id, start_request(batch).model_copy(update={"items": [bad_item]}), "operator", now=NOW)
    with pytest.raises(CustomerContactBlocked, match="NOT_FOUND"):
        service.start_batch(OTHER, batch.batch_id, start_request(batch), "operator", now=NOW)


def test_unknown_observation_keeps_frequency_reservation_and_view_conserves_items():
    service, store, batch = service_fixture()
    started = service.start_batch(SCOPE, batch.batch_id, start_request(batch), "operator", now=NOW)
    binding = started.items[0]
    receipt = ref("ActionReceipt", "receipt-1", "f")
    store.receipts[(*SCOPE.key, receipt.resource_id)] = (receipt.content_hash, binding.binding_hash)
    service.record_dispatch_observation(SCOPE, RecordCustomerDispatchObservationRequest(
        startDecisionRef=full_ref("CustomerBatchStartDecisionRevision", started.decision_id, started.content_hash),
        itemKey=binding.item_key, actionReceiptRef=receipt, state="unknown", observedAt=NOW,
    ))
    view = service.contribution_view(SCOPE, now=NOW)
    assert view.ledger.frozen_eligible == view.ledger.unknown == 1
    assert view.latest_start and view.latest_start.items[0].reservation and view.latest_start.items[0].reservation.status == "held"
    assert view.permit_redemption_allowed is view.contact_resolution_allowed is view.provider_dispatch_allowed is view.send_allowed is view.external_effects_allowed is False
    with pytest.raises(ValueError, match="cannot self-resolve"):
        RecordCustomerDispatchObservationRequest(
            startDecisionRef=full_ref("CustomerBatchStartDecisionRevision", started.decision_id, started.content_hash),
            itemKey=binding.item_key, actionReceiptRef=receipt, state="unknown", resolvedState="applied", observedAt=NOW,
        )


def test_cross_batch_frequency_reservation_fails_closed_when_rolling_limit_is_exhausted():
    service, store, batch = service_fixture()
    service.create_frequency_policy(SCOPE, CreateCustomerFrequencyPolicyRequest(
        policyId="frequency-policy", revision=1, channel="wecom", purpose="retention", timezone="Asia/Shanghai",
        quietHoursStart="22:00", quietHoursEnd="08:00", rollingWindowHours=168, maximumContacts=1,
    ), "operator", now=NOW)
    service.start_batch(SCOPE, batch.batch_id, start_request(batch), "operator", now=NOW)
    second = batch.model_copy(update={"batch_id": "batch-2"})
    service.batch_store.batch = second
    with pytest.raises(CustomerContactBlocked, match="FREQUENCY_LIMIT_EXCEEDED"):
        service.start_batch(SCOPE, second.batch_id, start_request(second), "operator", now=NOW)
    assert len(store.reservations) == 1


def test_dispatch_observation_cannot_manufacture_reserved_or_self_resolved_unknown_state():
    decision = full_ref("CustomerBatchStartDecisionRevision", "start-1", "a" * 64)
    receipt = ref("ActionReceipt", "receipt-1")
    with pytest.raises(ValueError, match="cannot manufacture pre-dispatch state"):
        RecordCustomerDispatchObservationRequest(startDecisionRef=decision, itemKey="item-1", actionReceiptRef=receipt, state="reserved", observedAt=NOW)
    with pytest.raises(ValueError, match="exact manual case"):
        RecordCustomerDispatchObservationRequest(startDecisionRef=decision, itemKey="item-1", actionReceiptRef=receipt, state="disputed", resolvedState="applied", observedAt=NOW)
