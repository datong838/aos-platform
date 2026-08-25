"""W6-03 canonical creator discovery, matching and batch-prepare contracts/service.

This module deliberately stops at a frozen, side-effect-free batch.  It does not
create ActionProposal, ExecutionLease, provider calls, outreach, samples,
contracts or commission changes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorExactRef
from aos_api.tenant_scope import TenantScope


CREATOR_PREPARE_SCHEMA_VERSION = "aos.ecommerce-workshop.creator-prepare/v1"
CREATOR_LOGIC_ID = "ecommerce-creator-match"
CREATOR_SKILL_IDS = (
    "frame-recruitment-brief",
    "build-evidence-pack",
    "segment-entities",
    CREATOR_LOGIC_ID,
    "compare-alternatives",
    "plan-responsibilities",
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class CreatorPrepareBlocked(RuntimeError):
    code = "CREATOR_PREPARE_BLOCKED"


class CreatorPrepareConflict(CreatorPrepareBlocked):
    code = "CREATOR_PREPARE_CONFLICT"


class CreatorSourceLicense(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"


class IdentityResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    CONFLICT = "conflict"


class MatchConfidence(StrEnum):
    PRELIMINARY = "preliminary"
    CONFIRMED = "confirmed"


class BatchItemDisposition(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"
    DEDUPLICATED = "deduplicated"


class CreatorDiscoveryProfileRequest(AipContractModel):
    profile_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    allowed_source_kinds: list[str] = Field(min_length=1, max_length=32)
    required_fact_keys: list[str] = Field(min_length=1, max_length=64)
    output_schema_ref: CreatorExactRef
    freshness_seconds: int = Field(ge=60, le=2_592_000)
    retention_days: int = Field(ge=1, le=3650)
    minimum_disclosure: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def _canonical_profile(self) -> CreatorDiscoveryProfileRequest:
        for values in (self.allowed_source_kinds, self.required_fact_keys, self.minimum_disclosure):
            if len(values) != len(set(values)) or any(not value.strip() for value in values):
                raise ValueError("creator discovery profile lists must be unique and non-empty")
        if self.output_schema_ref.resource_type != "SchemaRevision":
            raise ValueError("outputSchemaRef must reference SchemaRevision")
        return self


class CreatorDiscoveryProfileRevision(CreatorDiscoveryProfileRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class NormalizeCreatorArtifactRequest(AipContractModel):
    profile_ref: CreatorExactRef
    research_artifact_ref: CreatorExactRef
    source_kind: str = Field(min_length=1, max_length=120)
    source_license: CreatorSourceLicense
    source_fresh_at: datetime
    artifact_schema_ref: CreatorExactRef
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_record_refs: list[CreatorExactRef] = Field(min_length=1, max_length=100)
    stable_identity_keys: list[str] = Field(min_length=1, max_length=20)
    conflicting_identity_keys: list[str] = Field(default_factory=list, max_length=20)
    fact_keys: list[str] = Field(min_length=1, max_length=100)
    pii_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("source_fresh_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("sourceFreshAt must include timezone")
        return value

    @model_validator(mode="after")
    def _normalizer_input(self) -> NormalizeCreatorArtifactRequest:
        if self.profile_ref.resource_type != "CreatorDiscoveryProfileRevision":
            raise ValueError("profileRef must reference CreatorDiscoveryProfileRevision")
        if self.research_artifact_ref.resource_type != "ResearchArtifactRevision":
            raise ValueError("researchArtifactRef must reference ResearchArtifactRevision")
        if self.artifact_schema_ref.resource_type != "SchemaRevision":
            raise ValueError("artifactSchemaRef must reference SchemaRevision")
        if len(self.original_record_refs) != len({(x.resource_type, x.resource_id, x.revision, x.content_hash) for x in self.original_record_refs}):
            raise ValueError("originalRecordRefs must be unique")
        for values in (self.stable_identity_keys, self.conflicting_identity_keys, self.fact_keys, self.pii_refs):
            if len(values) != len(set(values)) or any(not value.strip() for value in values):
                raise ValueError("normalizer lists must be unique and non-empty")
        return self


class CreatorNormalizerReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    candidate_id: str
    revision: int = 1
    profile_ref: CreatorExactRef
    research_artifact_ref: CreatorExactRef
    original_record_refs: list[CreatorExactRef]
    identity_status: IdentityResolutionStatus
    identity_key_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    conflict_codes: list[str]
    fact_keys: list[str]
    pii_refs: list[str]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreateCreatorMatchObservationRequest(AipContractModel):
    candidate_ref: CreatorExactRef
    evidence_bundle_ref: CreatorExactRef
    feature_schema_ref: CreatorExactRef
    logic_ref: CreatorExactRef
    policy_ref: CreatorExactRef
    score: float = Field(ge=0, le=1)
    policy_threshold: float = Field(ge=0, le=1)
    feature_summaries: dict[str, float] = Field(min_length=1, max_length=64)
    missing_fact_keys: list[str] = Field(default_factory=list, max_length=64)
    identity_status: IdentityResolutionStatus

    @model_validator(mode="after")
    def _typed_refs(self) -> CreateCreatorMatchObservationRequest:
        expected = {
            "candidate_ref": "CreatorCandidateRevision",
            "evidence_bundle_ref": "EvidenceBundleRevision",
            "feature_schema_ref": "FeatureSchemaRevision",
            "logic_ref": "LogicPublicationRevision",
            "policy_ref": "CreatorMatchPolicyRevision",
        }
        for field, resource_type in expected.items():
            if getattr(self, field).resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        if len(self.missing_fact_keys) != len(set(self.missing_fact_keys)):
            raise ValueError("missingFactKeys must be unique")
        return self


class CreatorPreparedMatchObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str
    revision: int = 1
    candidate_ref: CreatorExactRef
    evidence_bundle_ref: CreatorExactRef
    feature_schema_ref: CreatorExactRef
    logic_ref: CreatorExactRef
    policy_ref: CreatorExactRef
    score: float
    policy_threshold: float
    confidence: MatchConfidence
    feature_summaries: dict[str, float]
    missing_fact_keys: list[str]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class DecideCreatorMatchRequest(AipContractModel):
    observation_ref: CreatorExactRef
    decision: str = Field(pattern=r"^(accepted|rejected|needs_review)$")
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")

    @model_validator(mode="after")
    def _observation_ref(self) -> DecideCreatorMatchRequest:
        if self.observation_ref.resource_type != "CreatorPreparedMatchObservation":
            raise ValueError("observationRef must reference CreatorPreparedMatchObservation")
        return self


class CreatorPreparedMatchDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    revision: int = 1
    observation_ref: CreatorExactRef
    disposition: str
    reason_code: str
    decided_by: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decided_at: datetime


class PrepareCreatorBatchItem(AipContractModel):
    candidate_ref: CreatorExactRef
    evidence_bundle_ref: CreatorExactRef
    match_observation_ref: CreatorExactRef
    match_decision_ref: CreatorExactRef
    disposition: BatchItemDisposition
    reason_codes: list[str] = Field(default_factory=list, max_length=32)
    frequency_eligible: bool
    capacity_eligible: bool
    budget_eligible: bool

    @model_validator(mode="after")
    def _item_refs(self) -> PrepareCreatorBatchItem:
        expected = (
            (self.candidate_ref, "CreatorCandidateRevision"),
            (self.evidence_bundle_ref, "EvidenceBundleRevision"),
            (self.match_observation_ref, "CreatorPreparedMatchObservation"),
            (self.match_decision_ref, "CreatorPreparedMatchDecision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("batch item exact refs have invalid resourceType")
        gates = self.frequency_eligible and self.capacity_eligible and self.budget_eligible
        if self.disposition is BatchItemDisposition.ELIGIBLE and not gates:
            raise ValueError("eligible batch item requires frequency/capacity/budget")
        if self.disposition is not BatchItemDisposition.ELIGIBLE and not self.reason_codes:
            raise ValueError("non-eligible batch item requires reasonCodes")
        return self


class PrepareCreatorBatchRequest(AipContractModel):
    batch_id: str = Field(min_length=1, max_length=200)
    brief_ref: CreatorExactRef
    eval_ref: CreatorExactRef
    responsibility_plan_ref: CreatorExactRef
    frequency_policy_ref: CreatorExactRef
    capacity_snapshot_ref: CreatorExactRef
    budget_snapshot_ref: CreatorExactRef
    skill_refs: list[CreatorExactRef] = Field(min_length=6, max_length=16)
    logic_ref: CreatorExactRef
    agent_binding_ref: CreatorExactRef
    items: list[PrepareCreatorBatchItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _exact_composition(self) -> PrepareCreatorBatchRequest:
        refs = {
            "brief_ref": "TaskBriefRevision", "eval_ref": "EvalContractRevision",
            "responsibility_plan_ref": "ResponsibilityPlanRevision",
            "frequency_policy_ref": "FrequencyPolicyRevision",
            "capacity_snapshot_ref": "CapacitySnapshotRevision",
            "budget_snapshot_ref": "BudgetSnapshotRevision",
            "logic_ref": "LogicPublicationRevision", "agent_binding_ref": "AgentBindingRevision",
        }
        for field, resource_type in refs.items():
            if getattr(self, field).resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        if {ref.resource_id for ref in self.skill_refs} != set(CREATOR_SKILL_IDS):
            raise ValueError("skillRefs must cover the canonical creator composition")
        if any(ref.resource_type != "SkillRevision" for ref in self.skill_refs):
            raise ValueError("skillRefs must reference SkillRevision")
        if self.logic_ref.resource_id != CREATOR_LOGIC_ID:
            raise ValueError("logicRef must be ecommerce-creator-match")
        candidates = [item.candidate_ref.resource_id for item in self.items]
        if len(candidates) != len(set(candidates)):
            raise ValueError("duplicate candidates must be represented as deduplicated items, not repeated rows")
        return self


class CreatorBatchCountLedger(AipContractModel):
    input: int = Field(ge=0)
    eligible: int = Field(ge=0)
    excluded: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    unknown: int = Field(ge=0)
    deduplicated: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserved(self) -> CreatorBatchCountLedger:
        if self.input != self.eligible + self.excluded + self.needs_review + self.unknown + self.deduplicated:
            raise ValueError("creator batch item ledger must conserve input")
        return self


class CreatorBatchPreparationRevision(AipContractModel):
    tenant: TenantContext
    batch_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    lifecycle: str = Field(pattern=r"^(prepared|frozen|stale)$")
    exact_refs: dict[str, CreatorExactRef]
    skill_refs: list[CreatorExactRef]
    items: list[PrepareCreatorBatchItem] = Field(default_factory=list, max_length=100)
    item_hashes: list[str]
    ledger: CreatorBatchCountLedger
    external_effect_count: int = Field(default=0, ge=0, le=0)
    action_proposal_count: int = Field(default=0, ge=0, le=0)
    execution_lease_count: int = Field(default=0, ge=0, le=0)
    prior_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class FreezeCreatorBatchRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_refs: dict[str, CreatorExactRef]


class CreatorContributionView(AipContractModel):
    schema_version: str = CREATOR_PREPARE_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    atomic_skill_refs: list[CreatorExactRef]
    logic_ref: CreatorExactRef | None
    primary_colleague: str = "导购顾问"
    collaborator_colleagues: list[str] = Field(default_factory=lambda: ["数据参谋", "内容官", "活动策划师"])
    latest_batch: CreatorBatchPreparationRevision | None
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: ["PREPARE_CREATOR_BATCH", "FREEZE_CREATOR_BATCH"])
    external_effects_allowed: bool = False


class EcommerceWorkshopCreatorPrepareService:
    def __init__(self, store: Any) -> None:
        self.store = store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    def create_profile(self, scope: TenantScope, request: CreatorDiscoveryProfileRequest, actor: str, *, now: datetime | None = None) -> CreatorDiscoveryProfileRevision:
        at = now or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        item = CreatorDiscoveryProfileRevision(tenant=self._tenant(scope), **payload, contentHash=canonical_hash(payload), createdBy=actor, createdAt=at)
        return self.store.append_profile(scope, item)

    def normalize(self, scope: TenantScope, request: NormalizeCreatorArtifactRequest, actor: str, *, now: datetime | None = None) -> CreatorNormalizerReceipt:
        at = now or datetime.now(UTC)
        profile = self.store.require_profile(scope, request.profile_ref)
        if request.source_license is not CreatorSourceLicense.ALLOWED:
            raise CreatorPrepareBlocked("CREATOR_SOURCE_LICENSE_NOT_ALLOWED")
        if request.source_kind not in profile.allowed_source_kinds:
            raise CreatorPrepareBlocked("CREATOR_SOURCE_KIND_NOT_ALLOWED")
        if request.artifact_schema_ref != profile.output_schema_ref:
            raise CreatorPrepareBlocked("CREATOR_ARTIFACT_SCHEMA_DRIFTED")
        age = (at - request.source_fresh_at).total_seconds()
        if age < 0 or age > profile.freshness_seconds:
            raise CreatorPrepareBlocked("CREATOR_SOURCE_STALE")
        missing = sorted(set(profile.required_fact_keys) - set(request.fact_keys))
        if missing:
            raise CreatorPrepareBlocked("CREATOR_REQUIRED_FACTS_MISSING:" + ",".join(missing))
        identity_status = IdentityResolutionStatus.CONFLICT if request.conflicting_identity_keys else IdentityResolutionStatus.RESOLVED
        identity_hash = canonical_hash(sorted(request.stable_identity_keys))
        base = request.model_dump(mode="json", by_alias=True)
        receipt_id = f"creator-normalize-{canonical_hash([*scope.key, base])[:24]}"
        candidate_id = f"creator-{identity_hash[:24]}"
        item = CreatorNormalizerReceipt(
            tenant=self._tenant(scope), receiptId=receipt_id, candidateId=candidate_id,
            profileRef=request.profile_ref, researchArtifactRef=request.research_artifact_ref,
            originalRecordRefs=request.original_record_refs, identityStatus=identity_status,
            identityKeyHash=identity_hash,
            conflictCodes=["CREATOR_IDENTITY_CONFLICT"] if request.conflicting_identity_keys else [],
            factKeys=sorted(request.fact_keys), piiRefs=request.pii_refs,
            contentHash=canonical_hash({**base, "candidateId": candidate_id, "identityStatus": identity_status}),
            createdBy=actor, createdAt=at,
        )
        return self.store.append_normalizer_receipt(scope, item)

    def observe_match(self, scope: TenantScope, request: CreateCreatorMatchObservationRequest, *, now: datetime | None = None) -> CreatorPreparedMatchObservation:
        at = now or datetime.now(UTC)
        preliminary = request.identity_status is IdentityResolutionStatus.CONFLICT or bool(request.missing_fact_keys) or request.score < request.policy_threshold
        payload = request.model_dump(mode="json", by_alias=True)
        payload.pop("identityStatus", None)
        item = CreatorPreparedMatchObservation(
            tenant=self._tenant(scope), observationId=f"creator-match-{canonical_hash([*scope.key, payload])[:24]}",
            **payload, confidence=MatchConfidence.PRELIMINARY if preliminary else MatchConfidence.CONFIRMED,
            contentHash=canonical_hash({**payload, "confidence": "preliminary" if preliminary else "confirmed"}), createdAt=at,
        )
        return self.store.append_match_observation(scope, item)

    def decide_match(self, scope: TenantScope, request: DecideCreatorMatchRequest, actor: str, *, now: datetime | None = None) -> CreatorPreparedMatchDecision:
        at = now or datetime.now(UTC)
        observation = self.store.require_match_observation(scope, request.observation_ref)
        if request.decision == "rejected" and observation.confidence is MatchConfidence.PRELIMINARY:
            raise CreatorPrepareBlocked("PRELIMINARY_MATCH_CANNOT_AUTO_REJECT")
        payload = request.model_dump(mode="json", by_alias=True)
        item = CreatorPreparedMatchDecision(
            tenant=self._tenant(scope), decisionId=f"creator-decision-{canonical_hash([*scope.key, payload, actor])[:24]}",
            observationRef=request.observation_ref, disposition=request.decision, reasonCode=request.reason_code,
            decidedBy=actor, contentHash=canonical_hash({**payload, "actor": actor}), decidedAt=at,
        )
        return self.store.append_match_decision(scope, item)

    def prepare_batch(self, scope: TenantScope, request: PrepareCreatorBatchRequest, actor: str, *, now: datetime | None = None) -> CreatorBatchPreparationRevision:
        at = now or datetime.now(UTC)
        counts = {item.value: 0 for item in BatchItemDisposition}
        for item in request.items:
            decision = self.store.require_match_decision(scope, item.match_decision_ref)
            if decision.observation_ref != item.match_observation_ref:
                raise CreatorPrepareBlocked("CREATOR_BATCH_MATCH_LINEAGE_DRIFTED")
            required_disposition = {
                BatchItemDisposition.ELIGIBLE: "accepted",
                BatchItemDisposition.NEEDS_REVIEW: "needs_review",
                BatchItemDisposition.EXCLUDED: "rejected",
                BatchItemDisposition.UNKNOWN: "needs_review",
                BatchItemDisposition.DEDUPLICATED: "accepted",
            }[item.disposition]
            if decision.disposition != required_disposition:
                raise CreatorPrepareBlocked("CREATOR_BATCH_DECISION_DISPOSITION_DRIFTED")
            counts[item.disposition.value] += 1
        exact_refs = {
            "brief": request.brief_ref, "eval": request.eval_ref,
            "responsibilityPlan": request.responsibility_plan_ref,
            "frequencyPolicy": request.frequency_policy_ref,
            "capacitySnapshot": request.capacity_snapshot_ref,
            "budgetSnapshot": request.budget_snapshot_ref,
            "logic": request.logic_ref, "agentBinding": request.agent_binding_ref,
        }
        payload = request.model_dump(mode="json", by_alias=True)
        item_hashes = [canonical_hash(item.model_dump(mode="json", by_alias=True)) for item in request.items]
        content_hash = canonical_hash({**payload, "itemHashes": item_hashes})
        existing = self.store.latest_batch_or_none_by_id(scope, request.batch_id)
        if existing is not None:
            if existing.lifecycle == "prepared" and existing.content_hash == content_hash:
                return existing
            raise CreatorPrepareConflict("CREATOR_BATCH_IDEMPOTENCY_CONFLICT")
        item = CreatorBatchPreparationRevision(
            tenant=self._tenant(scope), batchId=request.batch_id, revision=1,
            version=1, lifecycle="prepared", exactRefs=exact_refs, skillRefs=request.skill_refs,
            items=request.items,
            itemHashes=item_hashes,
            ledger=CreatorBatchCountLedger(input=len(request.items), **counts),
            contentHash=content_hash, createdBy=actor, createdAt=at,
        )
        return self.store.append_batch(scope, item)

    def freeze_batch(self, scope: TenantScope, batch_id: str, request: FreezeCreatorBatchRequest, actor: str, *, now: datetime | None = None) -> CreatorBatchPreparationRevision:
        at = now or datetime.now(UTC)
        current = self.store.latest_batch(scope, batch_id)
        if current.lifecycle == "frozen" and current.prior_content_hash == request.expected_content_hash:
            return current
        if current.version != request.expected_version or current.content_hash != request.expected_content_hash:
            raise CreatorPrepareConflict("CREATOR_BATCH_EXPECTED_VERSION_OR_HASH_DRIFTED")
        expected = {key: value.model_dump(mode="json", by_alias=True) for key, value in current.exact_refs.items()}
        actual = {key: value.model_dump(mode="json", by_alias=True) for key, value in request.exact_refs.items()}
        if actual != expected:
            raise CreatorPrepareBlocked("CREATOR_BATCH_EXACT_REFS_DRIFTED")
        if current.lifecycle != "prepared":
            raise CreatorPrepareConflict("CREATOR_BATCH_NOT_PREPARED")
        payload = current.model_dump(mode="json", by_alias=True)
        payload.update({"revision": current.revision + 1, "version": current.version + 1, "lifecycle": "frozen", "priorContentHash": current.content_hash, "createdBy": actor, "createdAt": at, "contentHash": canonical_hash({"prior": current.content_hash, "exactRefs": actual, "lifecycle": "frozen"})})
        return self.store.append_batch(scope, CreatorBatchPreparationRevision.model_validate(payload))

    def contribution_view(self, scope: TenantScope, *, now: datetime | None = None) -> CreatorContributionView:
        at = now or datetime.now(UTC)
        try:
            latest = self.store.latest_batch_or_none(scope)
        except CreatorPrepareBlocked as exc:
            if str(exc) != "CREATOR_PREPARE_AUTHORITY_UNAVAILABLE":
                raise
            return CreatorContributionView(
                tenant=self._tenant(scope),
                evaluatedAt=at,
                blockers=[
                    "CREATOR_PREPARE_AUTHORITY_UNAVAILABLE",
                    "CREATOR_BATCH_PREPARATION_NOT_AVAILABLE",
                ],
            )
        skill_refs = latest.skill_refs if latest else []
        logic_ref = latest.exact_refs.get("logic") if latest else None
        blockers = [] if latest else ["CREATOR_BATCH_PREPARATION_NOT_AVAILABLE"]
        if latest and latest.lifecycle != "frozen":
            blockers.append("CREATOR_BATCH_NOT_FROZEN")
        return CreatorContributionView(tenant=self._tenant(scope), evaluatedAt=at, atomicSkillRefs=skill_refs, logicRef=logic_ref, latestBatch=latest, blockers=blockers)


__all__ = [name for name in globals() if name.startswith("Creator") or name.startswith("Prepare") or name.startswith("Freeze") or name.startswith("Normalize") or name in {"BatchItemDisposition", "MatchConfidence", "IdentityResolutionStatus", "EcommerceWorkshopCreatorPrepareService", "canonical_hash"}]
