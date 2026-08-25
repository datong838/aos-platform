from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.ecommerce_workshop_customer_lifecycle import (
    ConsentDecision,
    CreateCustomerConsentPolicyRequest,
    CreateCustomerDialogueRequest,
    CreateCustomerJourneyRequest,
    CreateCustomerSegmentRequest,
    CustomerBatchDisposition,
    CustomerLifecycleBlocked,
    CustomerLifecycleConflict,
    EcommerceWorkshopCustomerLifecycleService,
    FreezeCustomerDialogueBatchRequest,
    PrepareCustomerDialogueBatchItem,
    PrepareCustomerDialogueBatchRequest,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, identity: str, digest: str = "a", revision: int = 1) -> CustomerExactRef:
    return CustomerExactRef(resourceType=kind, resourceId=identity, revision=revision, contentHash=f"sha256:{digest * 64}", receiptId=f"receipt-{identity}")


def exact(item, kind: str, identity_field: str) -> CustomerExactRef:
    identity = getattr(item, identity_field)
    return ref(kind, identity, item.content_hash[0], revision=item.revision)


class MemoryStore:
    def __init__(self):
        self.policies = {}; self.segments = {}; self.journeys = {}; self.dialogues = {}; self.batches = {}

    def append_consent_policy(self, _scope, item): self.policies[item.policy_id] = item; return item
    def append_segment(self, _scope, item): self.segments[item.segment_id] = item; return item
    def append_journey(self, _scope, item): self.journeys[item.journey_id] = item; return item
    def append_dialogue(self, _scope, item): self.dialogues[item.dialogue_id] = item; return item
    def append_batch(self, _scope, item): self.batches.setdefault(item.batch_id, []).append(item); return item
    def require_consent_policy(self, _scope, exact_ref): return self.policies[exact_ref.resource_id]
    def require_segment(self, _scope, exact_ref): return self.segments[exact_ref.resource_id]
    def require_journey(self, _scope, exact_ref): return self.journeys[exact_ref.resource_id]
    def require_dialogue(self, _scope, exact_ref): return self.dialogues[exact_ref.resource_id]
    def require_external_policy_authorities(self, _scope, frequency, capability):
        assert frequency.resource_type == "FrequencyPolicyRevision"
        assert capability.resource_type == "CapabilityBindingRevision"
    def latest_batch_or_none(self, _scope, identity): return self.batches.get(identity, [None])[-1]
    def latest_batch(self, _scope, identity): return self.batches[identity][-1]
    def latest_batch_or_none_any(self, _scope): return next((items[-1] for items in self.batches.values()), None)
    def authority_counts(self, _scope):
        return {"consent_policy": len(self.policies), "segment": len(self.segments), "journey": len(self.journeys), "dialogue": len(self.dialogues)}


def authority_fixture():
    store = MemoryStore(); service = EcommerceWorkshopCustomerLifecycleService(store)
    policy = service.create_consent_policy(SCOPE, CreateCustomerConsentPolicyRequest(
        policyId="consent-retention", revision=1, purpose="retention", allowedChannels=["wecom"],
        markingPolicyRef=ref("MarkingPolicyRevision", "marking"), retentionPolicyRef=ref("RetentionPolicyRevision", "retention"),
        preferencePolicyRef=ref("PreferencePolicyRevision", "preference"), retentionDays=365,
    ), "operator", now=NOW)
    policy_ref = exact(policy, "CustomerConsentPolicyRevision", "policy_id")
    segment = service.create_segment(SCOPE, CreateCustomerSegmentRequest(
        segmentId="repeat-buyers", revision=1, definitionHash="b" * 64, queryHash="c" * 64,
        schemaRef=ref("SegmentSchemaRevision", "segment-schema"),
        sourceRefs=[ref("CustomerLiteProjectionRevision", "customer-source")], consentPolicyRef=policy_ref,
        kAnonymityMinimum=5, cutoff=NOW,
    ), "operator", now=NOW)
    segment_ref = exact(segment, "CustomerSegmentRevision", "segment_id")
    eval_ref = ref("EvalContractRevision", "dialogue-eval")
    journey = service.create_journey(SCOPE, CreateCustomerJourneyRequest(
        journeyId="retention-journey", revision=1, segmentRef=segment_ref, stageDefinitionHash="d" * 64,
        entryConditionHash="e" * 64, exitConditionHash="f" * 64, stopConditions=["consent_withdrawn"],
        allowedChannels=["wecom"], evalRef=eval_ref, policyRef=ref("JourneyPolicyRevision", "journey-policy"),
    ), "operator", now=NOW)
    journey_ref = exact(journey, "CustomerJourneyRevision", "journey_id")
    dialogue = service.create_dialogue(SCOPE, CreateCustomerDialogueRequest(
        dialogueId="retention-dialogue", revision=1, journeyRef=journey_ref,
        briefRef=ref("TaskBriefRevision", "brief"), evidenceRef=ref("EvidenceBundleRevision", "evidence"),
        evalRef=eval_ref, responsibilityRef=ref("ResponsibilityPlanRevision", "responsibility"),
        templateRef=ref("TemplateRevision", "template"), strategyHash="1" * 64, originalsReachable=True,
    ), "operator", now=NOW)
    return store, service, policy_ref, segment_ref, journey_ref, exact(dialogue, "CustomerDialogueStrategyRevision", "dialogue_id")


def batch_request(policy_ref, segment_ref, journey_ref, dialogue_ref):
    return PrepareCustomerDialogueBatchRequest(
        batchId="batch-1", segmentRef=segment_ref, journeyRef=journey_ref, dialogueRef=dialogue_ref,
        consentPolicyRef=policy_ref, frequencyPolicyRef=ref("FrequencyPolicyRevision", "frequency"),
        channelCapabilityRef=ref("CapabilityBindingRevision", "capability"), items=[
            PrepareCustomerDialogueBatchItem(
                itemKey="item-1", customerRef=ref("CustomerLiteProjectionRevision", "customer-1"),
                disposition=CustomerBatchDisposition.ELIGIBLE, consentDecision=ConsentDecision.GRANTED,
                retentionActive=True, kAnonymitySatisfied=True,
                eligibilityEvidenceRefs=[ref("ConsentRevision", "consent-1")],
            ),
            PrepareCustomerDialogueBatchItem(
                itemKey="item-2", customerRef=ref("CustomerLiteProjectionRevision", "customer-2"),
                disposition=CustomerBatchDisposition.UNKNOWN, consentDecision=ConsentDecision.UNKNOWN,
                retentionActive=None, kAnonymitySatisfied=None, reasonCodes=["CONSENT_UNKNOWN"],
            ),
        ],
    )


def test_customer_authorities_and_batch_prepare_freeze_preserve_zero_effects():
    _store, service, policy_ref, segment_ref, journey_ref, dialogue_ref = authority_fixture()
    prepared = service.prepare_batch(SCOPE, batch_request(policy_ref, segment_ref, journey_ref, dialogue_ref), "operator", now=NOW)
    assert prepared.ledger.input == 2 and prepared.ledger.eligible == 1 and prepared.ledger.unknown == 1
    assert prepared.contact_resolution_count == prepared.action_count == prepared.provider_call_count == prepared.send_count == prepared.external_effect_count == 0
    exact_refs = {"segment": segment_ref, "journey": journey_ref, "dialogue": dialogue_ref, "consentPolicy": policy_ref, "frequencyPolicy": prepared.frequency_policy_ref, "channelCapability": prepared.channel_capability_ref}
    frozen = service.freeze_batch(SCOPE, prepared.batch_id, FreezeCustomerDialogueBatchRequest(
        expectedVersion=1, expectedContentHash=prepared.content_hash, exactRefs=exact_refs, itemHashes=prepared.item_hashes,
    ), "reviewer", now=NOW)
    assert frozen.lifecycle == "frozen" and frozen.version == 2 and frozen.prior_content_hash == prepared.content_hash
    assert frozen.send_count == frozen.external_effect_count == 0


def test_batch_drift_and_noneligible_without_reason_fail_closed():
    _store, service, policy_ref, segment_ref, journey_ref, dialogue_ref = authority_fixture()
    prepared = service.prepare_batch(SCOPE, batch_request(policy_ref, segment_ref, journey_ref, dialogue_ref), "operator", now=NOW)
    with pytest.raises(CustomerLifecycleConflict, match="EXACT_REFS_OR_ITEMS_DRIFTED"):
        service.freeze_batch(SCOPE, prepared.batch_id, FreezeCustomerDialogueBatchRequest(
            expectedVersion=1, expectedContentHash=prepared.content_hash,
            exactRefs={"segment": segment_ref}, itemHashes=prepared.item_hashes,
        ), "reviewer", now=NOW)
    with pytest.raises(ValueError, match="non-eligible item requires"):
        PrepareCustomerDialogueBatchItem(
            itemKey="bad", customerRef=ref("CustomerLiteProjectionRevision", "customer-bad"),
            disposition=CustomerBatchDisposition.EXCLUDED, consentDecision=ConsentDecision.WITHDRAWN,
            retentionActive=True, kAnonymitySatisfied=True,
        )


def test_contribution_view_exposes_atomic_skill_logic_and_colleague_binding():
    _store, service, policy_ref, segment_ref, journey_ref, dialogue_ref = authority_fixture()
    service.prepare_batch(SCOPE, batch_request(policy_ref, segment_ref, journey_ref, dialogue_ref), "operator", now=NOW)
    view = service.contribution_view(SCOPE, now=NOW)
    assert len(view.atomic_skill_ids) == 8 and view.logic_id == "ecommerce-customer-relationship"
    assert view.primary_colleague == "私域管家" and view.collaborator_colleagues == ["内容官", "客服专员", "导购顾问", "数据参谋"]
    assert view.contact_resolution_allowed is view.start_allowed is view.send_allowed is view.external_effects_allowed is False
    assert view.latest_batch is not None and "CUSTOMER_START_SEND_NOT_AUTHORIZED" in view.blockers
