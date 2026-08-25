"""W6-04 creator start and collaboration lifecycle authority.

The explicit start implemented here is a governance compilation point.  It
never calls a provider and never claims that an Action proposal, approval,
lease, receipt or external effect exists.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorExactRef
from aos_api.ecommerce_workshop_creator_prepare import (
    BatchItemDisposition,
    CreatorBatchPreparationRevision,
    canonical_hash,
)
from aos_api.tenant_scope import TenantScope


CREATOR_LIFECYCLE_SCHEMA_VERSION = "aos.ecommerce-workshop.creator-lifecycle/v1"


class CreatorLifecycleBlocked(RuntimeError):
    code = "CREATOR_LIFECYCLE_BLOCKED"


class CreatorLifecycleConflict(CreatorLifecycleBlocked):
    code = "CREATOR_LIFECYCLE_CONFLICT"


class CreatorActionKind(StrEnum):
    OUTREACH_MESSAGE = "outreach-message"
    SAMPLE_SHIPMENT = "sample-shipment"
    CONTRACT_SIGNATURE = "contract-signature"
    COMMISSION_CHANGE = "commission-change"


class CreatorLaneOutcome(StrEnum):
    PREPARED = "prepared"
    ACCEPTED = "accepted"
    APPLIED = "applied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"


class CreatorActionLaneRequest(AipContractModel):
    candidate_ref: CreatorExactRef
    action_kind: CreatorActionKind
    action_type_ref: CreatorExactRef
    impact_preview_ref: CreatorExactRef
    adapter_capability_ref: CreatorExactRef
    account_binding_ref: CreatorExactRef
    budget_reservation_ref: CreatorExactRef
    approval_policy_ref: CreatorExactRef

    @model_validator(mode="after")
    def _typed_refs(self) -> CreatorActionLaneRequest:
        expected = {
            "candidate_ref": "CreatorCandidateRevision",
            "action_type_ref": "ActionTypeRevision",
            "impact_preview_ref": "ImpactPreviewRevision",
            "adapter_capability_ref": "AdapterCapabilityRevision",
            "account_binding_ref": "AccountBindingRevision",
            "budget_reservation_ref": "ActionBudgetReservationRevision",
            "approval_policy_ref": "ApprovalPolicyRevision",
        }
        for field, resource_type in expected.items():
            if getattr(self, field).resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        if self.action_type_ref.resource_id != f"ecommerce.creator.{self.action_kind.value}":
            raise ValueError("actionTypeRef must match the creator action kind")
        return self


class StartCreatorBatchRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lanes: list[CreatorActionLaneRequest] = Field(min_length=4, max_length=400)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _unique_lanes(self) -> StartCreatorBatchRequest:
        keys = [(lane.candidate_ref.resource_id, lane.action_kind.value) for lane in self.lanes]
        if len(keys) != len(set(keys)):
            raise ValueError("creator action lanes must be unique per candidate and action kind")
        return self


class CreatorActionLaneBinding(CreatorActionLaneRequest):
    lane_id: str
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: CreatorLaneOutcome = CreatorLaneOutcome.PREPARED
    action_receipt_ref: CreatorExactRef | None = None
    resolved_outcome: CreatorLaneOutcome | None = None


class CreatorBatchStartLedger(AipContractModel):
    eligible_items: int = Field(ge=0)
    lanes: int = Field(ge=0)
    prepared: int = Field(ge=0)
    accepted: int = Field(ge=0)
    applied: int = Field(ge=0)
    failed: int = Field(ge=0)
    unknown: int = Field(ge=0)
    disputed: int = Field(ge=0)
    completed: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserved(self) -> CreatorBatchStartLedger:
        if self.lanes != self.prepared + self.accepted + self.applied + self.failed + self.unknown + self.disputed:
            raise ValueError("creator start lane ledger must conserve lanes")
        if self.completed != self.applied + self.failed:
            raise ValueError("only applied and failed lanes are completed")
        return self


class CreatorBatchStartDecisionRevision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    revision: int = 1
    version: int = 1
    lifecycle: str = Field(pattern=r"^governance_prepared$")
    batch_ref: CreatorExactRef
    batch_item_hashes: list[str]
    lanes: list[CreatorActionLaneBinding]
    ledger: CreatorBatchStartLedger
    operational_blockers: list[str]
    external_effect_count: int = Field(default=0, ge=0, le=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_by: str
    started_at: datetime


class RecordCreatorLaneObservationRequest(AipContractModel):
    start_decision_ref: CreatorExactRef
    lane_id: str = Field(min_length=1, max_length=240)
    action_receipt_ref: CreatorExactRef
    outcome: CreatorLaneOutcome
    resolved_outcome: CreatorLaneOutcome | None = None
    manual_case_ref: CreatorExactRef | None = None
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _receipt_contract(self) -> RecordCreatorLaneObservationRequest:
        if self.start_decision_ref.resource_type != "CreatorBatchStartDecisionRevision":
            raise ValueError("startDecisionRef must reference CreatorBatchStartDecisionRevision")
        if self.action_receipt_ref.resource_type != "ActionReceipt":
            raise ValueError("actionReceiptRef must reference ActionReceipt")
        if self.manual_case_ref and self.manual_case_ref.resource_type != "ManualReconcileCase":
            raise ValueError("manualCaseRef must reference ManualReconcileCase")
        if self.outcome is CreatorLaneOutcome.UNKNOWN and self.resolved_outcome is not None:
            raise ValueError("unknown observation cannot self-declare a resolved outcome")
        if self.resolved_outcome in {CreatorLaneOutcome.PREPARED, CreatorLaneOutcome.ACCEPTED, CreatorLaneOutcome.UNKNOWN}:
            raise ValueError("resolvedOutcome must be terminal or disputed")
        return self


class CreatorLaneObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str
    revision: int = 1
    start_decision_ref: CreatorExactRef
    lane_id: str
    action_receipt_ref: CreatorExactRef
    outcome: CreatorLaneOutcome
    resolved_outcome: CreatorLaneOutcome | None = None
    manual_case_ref: CreatorExactRef | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime


class CreatorContractRevision(AipContractModel):
    tenant: TenantContext
    collaboration_id: str
    revision: int = Field(ge=1)
    candidate_ref: CreatorExactRef
    start_decision_ref: CreatorExactRef
    prior_contract_ref: CreatorExactRef | None = None
    terms_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    monetary_terms_ref: CreatorExactRef
    lifecycle: str = Field(pattern=r"^(draft|reviewed|signed_observed|cancelled)$")
    diff_fields: list[str] = Field(default_factory=list, max_length=64)
    action_receipt_ref: CreatorExactRef | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreateCreatorContractRevisionRequest(AipContractModel):
    collaboration_id: str = Field(min_length=1, max_length=200)
    candidate_ref: CreatorExactRef
    start_decision_ref: CreatorExactRef
    prior_contract_ref: CreatorExactRef | None = None
    terms_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    monetary_terms_ref: CreatorExactRef
    lifecycle: str = Field(pattern=r"^(draft|reviewed|signed_observed|cancelled)$")
    diff_fields: list[str] = Field(default_factory=list, max_length=64)
    action_receipt_ref: CreatorExactRef | None = None

    @model_validator(mode="after")
    def _refs(self) -> CreateCreatorContractRevisionRequest:
        expected = (
            (self.candidate_ref, "CreatorCandidateRevision"),
            (self.start_decision_ref, "CreatorBatchStartDecisionRevision"),
            (self.monetary_terms_ref, "ProtectedMonetaryTermsRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("creator contract exact ref type drifted")
        if self.prior_contract_ref and self.prior_contract_ref.resource_type != "CreatorContractRevision":
            raise ValueError("priorContractRef must reference CreatorContractRevision")
        if self.action_receipt_ref and self.action_receipt_ref.resource_type != "ActionReceipt":
            raise ValueError("actionReceiptRef must reference ActionReceipt")
        if self.lifecycle == "signed_observed" and self.action_receipt_ref is None:
            raise ValueError("signed_observed requires a canonical ActionReceipt")
        if len(self.diff_fields) != len(set(self.diff_fields)):
            raise ValueError("diffFields must be unique")
        return self


class CreatorDeliveryObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str
    collaboration_id: str
    contract_ref: CreatorExactRef
    delivery_ref: CreatorExactRef
    evidence_bundle_ref: CreatorExactRef
    sequence: int = Field(ge=1)
    status: str = Field(pattern=r"^(expected|in_transit|received|accepted|disputed)$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime


class RecordCreatorDeliveryRequest(AipContractModel):
    collaboration_id: str = Field(min_length=1, max_length=200)
    contract_ref: CreatorExactRef
    delivery_ref: CreatorExactRef
    evidence_bundle_ref: CreatorExactRef
    sequence: int = Field(ge=1)
    status: str = Field(pattern=r"^(expected|in_transit|received|accepted|disputed)$")
    observed_at: datetime

    @model_validator(mode="after")
    def _refs(self) -> RecordCreatorDeliveryRequest:
        expected = (
            (self.contract_ref, "CreatorContractRevision"),
            (self.delivery_ref, "DeliveryRevision"),
            (self.evidence_bundle_ref, "EvidenceBundleRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("creator delivery exact ref type drifted")
        return self


class CreatorRelationshipRevision(AipContractModel):
    tenant: TenantContext
    relationship_id: str
    revision: int = Field(ge=1)
    collaboration_id: str
    contract_ref: CreatorExactRef
    delivery_observation_refs: list[CreatorExactRef]
    maturity_policy_ref: CreatorExactRef
    maturity_window_ends_at: datetime
    status: str = Field(pattern=r"^(preliminary|mature|at_risk)$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class CreateCreatorRelationshipRevisionRequest(AipContractModel):
    relationship_id: str = Field(min_length=1, max_length=200)
    collaboration_id: str = Field(min_length=1, max_length=200)
    contract_ref: CreatorExactRef
    delivery_observation_refs: list[CreatorExactRef] = Field(default_factory=list, max_length=100)
    maturity_policy_ref: CreatorExactRef
    maturity_window_ends_at: datetime
    status: str = Field(pattern=r"^(preliminary|mature|at_risk)$")

    @model_validator(mode="after")
    def _refs(self) -> CreateCreatorRelationshipRevisionRequest:
        if self.contract_ref.resource_type != "CreatorContractRevision":
            raise ValueError("contractRef must reference CreatorContractRevision")
        if any(ref.resource_type != "CreatorDeliveryObservation" for ref in self.delivery_observation_refs):
            raise ValueError("deliveryObservationRefs must reference CreatorDeliveryObservation")
        if self.maturity_policy_ref.resource_type != "RelationshipMaturityPolicyRevision":
            raise ValueError("maturityPolicyRef must reference RelationshipMaturityPolicyRevision")
        keys = [(ref.resource_id, ref.revision, ref.content_hash) for ref in self.delivery_observation_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("deliveryObservationRefs must be unique")
        if self.maturity_window_ends_at.utcoffset() is None:
            raise ValueError("maturityWindowEndsAt must include timezone")
        return self


class CreatorLifecycleView(AipContractModel):
    schema_version: str = CREATOR_LIFECYCLE_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    latest_start: CreatorBatchStartDecisionRevision | None
    ledger: CreatorBatchStartLedger
    contracts: list[CreatorContractRevision]
    deliveries: list[CreatorDeliveryObservation]
    relationships: list[CreatorRelationshipRevision]
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: ["START_CREATOR_BATCH_GOVERNANCE"])
    external_effects_allowed: bool = False


def _ledger(lanes: list[CreatorActionLaneBinding], eligible: int) -> CreatorBatchStartLedger:
    counts = {outcome.value: 0 for outcome in CreatorLaneOutcome}
    for lane in lanes:
        counts[(lane.resolved_outcome or lane.outcome).value] += 1
    return CreatorBatchStartLedger(
        eligibleItems=eligible,
        lanes=len(lanes),
        **counts,
        completed=counts[CreatorLaneOutcome.APPLIED.value] + counts[CreatorLaneOutcome.FAILED.value],
    )


class EcommerceWorkshopCreatorLifecycleService:
    def __init__(self, store: Any, batch_store: Any) -> None:
        self.store = store
        self.batch_store = batch_store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _batch_ref(batch: CreatorBatchPreparationRevision) -> CreatorExactRef:
        return CreatorExactRef(resourceType="CreatorBatchPreparationRevision", resourceId=batch.batch_id, revision=batch.revision, contentHash=batch.content_hash)

    def start_batch(self, scope: TenantScope, batch_id: str, request: StartCreatorBatchRequest, actor: str, *, now: datetime | None = None) -> CreatorBatchStartDecisionRevision:
        at = now or datetime.now(UTC)
        batch = self.batch_store.latest_batch(scope, batch_id)
        if batch.lifecycle != "frozen":
            raise CreatorLifecycleBlocked("CREATOR_BATCH_NOT_FROZEN")
        if batch.version != request.expected_version or batch.content_hash != request.expected_content_hash:
            raise CreatorLifecycleConflict("CREATOR_BATCH_EXPECTED_VERSION_OR_HASH_DRIFTED")
        if not batch.items:
            raise CreatorLifecycleBlocked("CREATOR_BATCH_ITEMS_NOT_AVAILABLE")
        eligible = [item for item in batch.items if item.disposition is BatchItemDisposition.ELIGIBLE]
        expected = {(item.candidate_ref.resource_id, kind.value) for item in eligible for kind in CreatorActionKind}
        actual = {(lane.candidate_ref.resource_id, lane.action_kind.value) for lane in request.lanes}
        if actual != expected:
            raise CreatorLifecycleBlocked("CREATOR_ACTION_LANE_COVERAGE_DRIFTED")
        eligible_refs = {item.candidate_ref.resource_id: item.candidate_ref for item in eligible}
        if any(lane.candidate_ref != eligible_refs.get(lane.candidate_ref.resource_id) for lane in request.lanes):
            raise CreatorLifecycleBlocked("CREATOR_ACTION_LANE_CANDIDATE_REF_DRIFTED")
        bindings: list[CreatorActionLaneBinding] = []
        for lane in sorted(request.lanes, key=lambda value: (value.candidate_ref.resource_id, value.action_kind.value)):
            self.store.require_lane_authorities(scope, lane)
            payload = lane.model_dump(mode="json", by_alias=True)
            binding_hash = canonical_hash(payload)
            bindings.append(CreatorActionLaneBinding(**payload, laneId=f"creator-lane-{binding_hash[:24]}", bindingHash=binding_hash))
        decision_payload = {
            "batchRef": self._batch_ref(batch).model_dump(mode="json", by_alias=True),
            "batchItemHashes": batch.item_hashes,
            "lanes": [lane.model_dump(mode="json", by_alias=True) for lane in bindings],
            "reason": request.reason,
        }
        content_hash = canonical_hash(decision_payload)
        existing = self.store.latest_start_or_none(scope, batch_id)
        if existing is not None:
            if existing.content_hash == content_hash:
                return existing
            raise CreatorLifecycleConflict("CREATOR_BATCH_START_IDEMPOTENCY_CONFLICT")
        item = CreatorBatchStartDecisionRevision(
            tenant=self._tenant(scope), decisionId=f"creator-start-{canonical_hash([*scope.key, batch_id])[:24]}",
            lifecycle="governance_prepared", batchRef=self._batch_ref(batch), batchItemHashes=batch.item_hashes,
            lanes=bindings, ledger=_ledger(bindings, len(eligible)),
            operationalBlockers=["CREATOR_PRODUCTION_ADAPTER_NOT_AUTHORIZED", "CREATOR_EXTERNAL_EFFECT_NOT_AUTHORIZED"],
            contentHash=content_hash, startedBy=actor, startedAt=at,
        )
        return self.store.append_start(scope, batch_id, item)

    def record_lane_observation(self, scope: TenantScope, request: RecordCreatorLaneObservationRequest) -> CreatorLaneObservation:
        start = self.store.require_start(scope, request.start_decision_ref)
        lane = next((item for item in start.lanes if item.lane_id == request.lane_id), None)
        if lane is None:
            raise CreatorLifecycleBlocked("CREATOR_ACTION_LANE_NOT_FOUND")
        self.store.require_action_receipt(scope, request.action_receipt_ref, lane.binding_hash)
        payload = request.model_dump(mode="json", by_alias=True)
        item = CreatorLaneObservation(
            tenant=self._tenant(scope), observationId=f"creator-lane-observation-{canonical_hash(payload)[:24]}",
            **payload, contentHash=canonical_hash(payload),
        )
        return self.store.append_lane_observation(scope, item)

    def create_contract(self, scope: TenantScope, request: CreateCreatorContractRevisionRequest, actor: str, *, now: datetime | None = None) -> CreatorContractRevision:
        at = now or datetime.now(UTC)
        start = self.store.require_start(scope, request.start_decision_ref)
        lane = next((item for item in start.lanes if item.candidate_ref == request.candidate_ref and item.action_kind is CreatorActionKind.CONTRACT_SIGNATURE), None)
        if lane is None:
            raise CreatorLifecycleBlocked("CREATOR_CONTRACT_LANE_NOT_FOUND")
        prior = None
        if request.prior_contract_ref:
            prior = self.store.require_contract(scope, request.prior_contract_ref)
            if prior.collaboration_id != request.collaboration_id or prior.candidate_ref != request.candidate_ref:
                raise CreatorLifecycleBlocked("CREATOR_CONTRACT_LINEAGE_DRIFTED")
        if request.action_receipt_ref:
            self.store.require_action_receipt(scope, request.action_receipt_ref, lane.binding_hash)
        revision = 1 if prior is None else prior.revision + 1
        payload = request.model_dump(mode="json", by_alias=True)
        item = CreatorContractRevision(
            tenant=self._tenant(scope), revision=revision, **payload,
            contentHash=canonical_hash({**payload, "revision": revision}), createdBy=actor, createdAt=at,
        )
        return self.store.append_contract(scope, item)

    def record_delivery(self, scope: TenantScope, request: RecordCreatorDeliveryRequest) -> CreatorDeliveryObservation:
        contract = self.store.require_contract(scope, request.contract_ref)
        if contract.collaboration_id != request.collaboration_id:
            raise CreatorLifecycleBlocked("CREATOR_DELIVERY_COLLABORATION_DRIFTED")
        payload = request.model_dump(mode="json", by_alias=True)
        item = CreatorDeliveryObservation(
            tenant=self._tenant(scope), observationId=f"creator-delivery-{canonical_hash(payload)[:24]}",
            **payload, contentHash=canonical_hash(payload),
        )
        return self.store.append_delivery(scope, item)

    def create_relationship(self, scope: TenantScope, request: CreateCreatorRelationshipRevisionRequest, *, now: datetime | None = None) -> CreatorRelationshipRevision:
        at = now or datetime.now(UTC)
        contract = self.store.require_contract(scope, request.contract_ref)
        if contract.collaboration_id != request.collaboration_id:
            raise CreatorLifecycleBlocked("CREATOR_RELATIONSHIP_COLLABORATION_DRIFTED")
        for ref in request.delivery_observation_refs:
            delivery = self.store.require_delivery(scope, ref)
            if delivery.collaboration_id != request.collaboration_id:
                raise CreatorLifecycleBlocked("CREATOR_RELATIONSHIP_DELIVERY_LINEAGE_DRIFTED")
        if request.status == "mature" and (at < request.maturity_window_ends_at or not request.delivery_observation_refs):
            raise CreatorLifecycleBlocked("CREATOR_RELATIONSHIP_MATURITY_WINDOW_NOT_SATISFIED")
        prior = self.store.latest_relationship_or_none(scope, request.relationship_id)
        revision = 1 if prior is None else prior.revision + 1
        payload = request.model_dump(mode="json", by_alias=True)
        item = CreatorRelationshipRevision(
            tenant=self._tenant(scope), revision=revision, **payload,
            contentHash=canonical_hash({**payload, "revision": revision}), createdAt=at,
        )
        return self.store.append_relationship(scope, item)

    def view(self, scope: TenantScope, *, now: datetime | None = None) -> CreatorLifecycleView:
        at = now or datetime.now(UTC)
        try:
            start = self.store.latest_start_for_tenant_or_none(scope)
            observations = self.store.list_lane_observations(scope, start.decision_id) if start else []
            contracts = self.store.list_contracts(scope)
            deliveries = self.store.list_deliveries(scope)
            relationships = self.store.list_relationships(scope)
        except CreatorLifecycleBlocked as exc:
            if str(exc) != "CREATOR_LIFECYCLE_AUTHORITY_UNAVAILABLE":
                raise
            return CreatorLifecycleView(
                tenant=self._tenant(scope), evaluatedAt=at, latestStart=None,
                ledger=_ledger([], 0), contracts=[], deliveries=[], relationships=[],
                blockers=["CREATOR_LIFECYCLE_AUTHORITY_UNAVAILABLE", "CREATOR_BATCH_START_NOT_AVAILABLE"],
            )
        lanes = list(start.lanes) if start else []
        latest_by_lane: dict[str, CreatorLaneObservation] = {}
        for observation in observations:
            latest_by_lane[observation.lane_id] = observation
        if start:
            lanes = [lane.model_copy(update={"outcome": latest_by_lane[lane.lane_id].outcome, "resolved_outcome": latest_by_lane[lane.lane_id].resolved_outcome, "action_receipt_ref": latest_by_lane[lane.lane_id].action_receipt_ref}) if lane.lane_id in latest_by_lane else lane for lane in lanes]
            start = start.model_copy(update={"lanes": lanes, "ledger": _ledger(lanes, start.ledger.eligible_items)})
        blockers = list(start.operational_blockers) if start else ["CREATOR_BATCH_START_NOT_AVAILABLE"]
        return CreatorLifecycleView(
            tenant=self._tenant(scope), evaluatedAt=at, latestStart=start,
            ledger=_ledger(lanes, start.ledger.eligible_items if start else 0),
            contracts=contracts, deliveries=deliveries, relationships=relationships, blockers=blockers,
        )


__all__ = [name for name in globals() if name.startswith("Creator") or name.startswith("Start") or name.startswith("Record") or name in {"EcommerceWorkshopCreatorLifecycleService", "CREATOR_LIFECYCLE_SCHEMA_VERSION"}]
