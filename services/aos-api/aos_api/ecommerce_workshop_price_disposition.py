"""W6-06 typed price dispositions with no execution or external side effect."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef
from aos_api.ecommerce_workshop_price_research import PriceBatchDisposition, PriceResearchBatchRevision
from aos_api.tenant_scope import TenantScope


PRICE_DISPOSITION_SCHEMA_VERSION = "aos.ecommerce-workshop.price-disposition/v1"
PRICE_DISPOSITION_SKILL_IDS = (
    "compile-price-case",
    "prepare-price-advice",
    "prepare-price-notice",
    "prepare-price-handoff",
    "evaluate-reprice-specialized-gate",
)
PRICE_LOGIC_ID = "ecommerce-price-governance"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class PriceDispositionBlocked(RuntimeError):
    code = "PRICE_DISPOSITION_BLOCKED"


class PriceDispositionConflict(PriceDispositionBlocked):
    code = "PRICE_DISPOSITION_CONFLICT"


class PriceDispositionKind(StrEnum):
    INTERNAL_ADVICE = "internal_advice"
    EXTERNAL_NOTICE = "external_notice"
    MODULE_HANDOFF = "module_handoff"
    REPRICING = "repricing"


class PriceDispositionOutcome(StrEnum):
    PREPARED = "prepared"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    APPLIED = "applied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"


REQUIRED_GATE_TYPES: dict[PriceDispositionKind, dict[str, str]] = {
    PriceDispositionKind.INTERNAL_ADVICE: {
        "draftSchema": "SchemaRevision",
        "adoptionPolicy": "AdoptionPolicyRevision",
    },
    PriceDispositionKind.EXTERNAL_NOTICE: {
        "template": "TemplateRevision",
        "frequencyPolicy": "FrequencyPolicyRevision",
        "actionType": "ActionTypeRevision",
        "capabilityBinding": "CapabilityBindingRevision",
        "accountBinding": "AccountBindingRevision",
        "approvalPolicy": "ApprovalPolicyRevision",
        "budgetReservation": "BudgetReservation",
        "impactPreview": "ImpactPreviewRevision",
    },
    PriceDispositionKind.MODULE_HANDOFF: {
        "handoffContract": "HandoffContractRevision",
        "receiverModule": "WorkshopModuleRevision",
    },
    PriceDispositionKind.REPRICING: {
        "actionType": "ActionTypeRevision",
        "capabilityBinding": "CapabilityBindingRevision",
        "accountBinding": "AccountBindingRevision",
        "approvalPolicy": "ApprovalPolicyRevision",
        "budgetReservation": "BudgetReservation",
        "impactPreview": "ImpactPreviewRevision",
        "priceConstraints": "PriceConstraintPolicyRevision",
        "makerChecker": "MakerCheckerPolicyRevision",
        "killPolicy": "KillPolicyRevision",
        "canaryPlan": "CanaryPlanRevision",
        "compensationPolicy": "CompensationPolicyRevision",
    },
}


def _unique_refs(values: list[PriceExactRef], label: str) -> list[PriceExactRef]:
    keys = [(item.resource_type, item.resource_id, item.revision, item.content_hash) for item in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be unique")
    return values


class CreatePriceCaseRequest(AipContractModel):
    case_id: str = Field(min_length=1, max_length=200)
    batch_ref: PriceExactRef
    policy_ref: PriceExactRef
    evidence_bundle_ref: PriceExactRef
    eval_ref: PriceExactRef
    impact_preview_ref: PriceExactRef
    target_refs: list[PriceExactRef] = Field(min_length=1, max_length=100)
    calculation_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    anomaly_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    key_assumptions: list[str] = Field(default_factory=list, max_length=32)
    uncertainties: list[str] = Field(default_factory=list, max_length=32)
    detected_at: datetime

    @field_validator("detected_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("detectedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _refs(self) -> "CreatePriceCaseRequest":
        expected = (
            (self.batch_ref, "PriceResearchBatchRevision"),
            (self.policy_ref, "MonitoringPolicyRevision"),
            (self.evidence_bundle_ref, "EvidenceBundleRevision"),
            (self.eval_ref, "EvalContractRevision"),
            (self.impact_preview_ref, "ImpactPreviewRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("price case exact ref type drifted")
        if any(ref.resource_type != "ProductSkuRevision" for ref in self.target_refs):
            raise ValueError("targetRefs must reference ProductSkuRevision")
        _unique_refs(self.target_refs, "targetRefs")
        if len(self.key_assumptions) != len(set(self.key_assumptions)) or len(self.uncertainties) != len(set(self.uncertainties)):
            raise ValueError("assumptions and uncertainties must be unique")
        return self


class PriceCaseRevision(CreatePriceCaseRequest):
    tenant: TenantContext
    revision: int = Field(default=1, ge=1)
    lifecycle: str = Field(default="open", pattern=r"^(open|stale|closed)$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreatePriceDispositionContractRequest(AipContractModel):
    contract_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    kind: PriceDispositionKind
    payload_schema_ref: PriceExactRef
    risk_policy_ref: PriceExactRef

    @model_validator(mode="after")
    def _refs(self) -> "CreatePriceDispositionContractRequest":
        if self.payload_schema_ref.resource_type != "SchemaRevision" or self.risk_policy_ref.resource_type != "RiskPolicyRevision":
            raise ValueError("disposition contract schema/risk policy ref drifted")
        return self


class PriceDispositionContractRevision(CreatePriceDispositionContractRequest):
    tenant: TenantContext
    required_gate_types: dict[str, str]
    external_effect_capable: bool
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime

    @model_validator(mode="after")
    def _canonical_gate_contract(self) -> "PriceDispositionContractRevision":
        if self.required_gate_types != REQUIRED_GATE_TYPES[self.kind]:
            raise ValueError("requiredGateTypes drifted from canonical disposition contract")
        expected_capable = self.kind in {PriceDispositionKind.EXTERNAL_NOTICE, PriceDispositionKind.REPRICING}
        if self.external_effect_capable is not expected_capable:
            raise ValueError("externalEffectCapable drifted")
        return self


class PreparePriceDispositionRequest(AipContractModel):
    disposition_id: str = Field(min_length=1, max_length=200)
    case_ref: PriceExactRef
    contract_ref: PriceExactRef
    target_refs: list[PriceExactRef] = Field(min_length=1, max_length=100)
    gate_refs: dict[str, PriceExactRef]
    purpose: str = Field(min_length=1, max_length=500)
    requested_outcome: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _refs(self) -> "PreparePriceDispositionRequest":
        if self.case_ref.resource_type != "PriceCaseRevision" or self.contract_ref.resource_type != "PriceDispositionContractRevision":
            raise ValueError("disposition requires PriceCase and typed contract exact refs")
        if any(ref.resource_type != "ProductSkuRevision" for ref in self.target_refs):
            raise ValueError("targetRefs must reference ProductSkuRevision")
        _unique_refs(self.target_refs, "targetRefs")
        if len(self.gate_refs) != len(set(self.gate_refs)) or any(not key.strip() for key in self.gate_refs):
            raise ValueError("gateRefs keys must be unique and non-empty")
        return self


class PriceDispositionRevision(AipContractModel):
    tenant: TenantContext
    disposition_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    lifecycle: str = Field(pattern=r"^(prepared|frozen|stale)$")
    kind: PriceDispositionKind
    case_ref: PriceExactRef
    contract_ref: PriceExactRef
    target_refs: list[PriceExactRef]
    gate_refs: dict[str, PriceExactRef]
    purpose: str
    requested_outcome: str
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    operational_blockers: list[str]
    execution_allowed: bool = False
    provider_call_count: int = Field(default=0, ge=0, le=0)
    notification_send_count: int = Field(default=0, ge=0, le=0)
    repricing_count: int = Field(default=0, ge=0, le=0)
    external_effect_count: int = Field(default=0, ge=0, le=0)
    prior_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime

    @model_validator(mode="after")
    def _never_executes(self) -> "PriceDispositionRevision":
        if self.execution_allowed:
            raise ValueError("W6-06 disposition never grants execution")
        if self.kind is PriceDispositionKind.REPRICING and "PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED" not in self.operational_blockers:
            raise ValueError("repricing must retain its specialized operational blocker")
        return self


class FreezePriceDispositionRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_refs: dict[str, PriceExactRef]


class RecordPriceDispositionObservationRequest(AipContractModel):
    disposition_ref: PriceExactRef
    receipt_ref: PriceExactRef
    outcome: PriceDispositionOutcome
    resolved_outcome: PriceDispositionOutcome | None = None
    manual_case_ref: PriceExactRef | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def _honest_resolution(self) -> "RecordPriceDispositionObservationRequest":
        if self.disposition_ref.resource_type != "PriceDispositionRevision":
            raise ValueError("dispositionRef must reference PriceDispositionRevision")
        if self.observed_at.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        if self.outcome is PriceDispositionOutcome.UNKNOWN and self.resolved_outcome is not None:
            raise ValueError("unknown observation cannot self-resolve")
        if self.resolved_outcome is not None and self.manual_case_ref is None:
            raise ValueError("resolvedOutcome requires ManualReconcileCase")
        if self.manual_case_ref and self.manual_case_ref.resource_type != "ManualReconcileCase":
            raise ValueError("manualCaseRef must reference ManualReconcileCase")
        return self


class PriceDispositionObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str
    revision: int = 1
    disposition_ref: PriceExactRef
    receipt_ref: PriceExactRef
    outcome: PriceDispositionOutcome
    resolved_outcome: PriceDispositionOutcome | None = None
    manual_case_ref: PriceExactRef | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime


class PriceDispositionContributionView(AipContractModel):
    schema_version: str = PRICE_DISPOSITION_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    atomic_skill_ids: list[str] = Field(default_factory=lambda: list(PRICE_DISPOSITION_SKILL_IDS))
    logic_id: str = PRICE_LOGIC_ID
    primary_colleague: str = "数据参谋"
    collaborator_colleagues: list[str] = Field(default_factory=lambda: ["活动策划师", "导购顾问"])
    case_count: int = Field(ge=0)
    disposition_counts: dict[PriceDispositionKind, int]
    latest_disposition: PriceDispositionRevision | None
    latest_observation: PriceDispositionObservation | None
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: [
        "COMPILE_PRICE_CASE", "CREATE_PRICE_DISPOSITION_CONTRACT", "PREPARE_PRICE_DISPOSITION",
        "FREEZE_PRICE_DISPOSITION", "RECORD_PRICE_DISPOSITION_OBSERVATION",
    ])
    repricing_enabled: bool = False
    external_effects_allowed: bool = False


class EcommerceWorkshopPriceDispositionService:
    def __init__(self, store: Any, research_store: Any) -> None:
        self.store = store
        self.research_store = research_store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _batch_ref(batch: PriceResearchBatchRevision) -> PriceExactRef:
        return PriceExactRef(resourceType="PriceResearchBatchRevision", resourceId=batch.batch_id, revision=batch.revision, contentHash=f"sha256:{batch.content_hash}", receiptId=f"receipt-{batch.batch_id}")

    def create_case(self, scope: TenantScope, request: CreatePriceCaseRequest, actor: str, *, now: datetime | None = None) -> PriceCaseRevision:
        at = now or datetime.now(UTC)
        batch = self.research_store.latest_batch(scope, request.batch_ref.resource_id)
        if batch.lifecycle != "frozen" or self._batch_ref(batch) != request.batch_ref:
            raise PriceDispositionBlocked("PRICE_CASE_BATCH_MISSING_OR_DRIFTED")
        policy = self.research_store.require_policy(scope, request.policy_ref)
        if policy.eval_ref != request.eval_ref:
            raise PriceDispositionBlocked("PRICE_CASE_POLICY_EVAL_DRIFTED")
        if batch.exact_refs.get("monitoringPolicy") != request.policy_ref or batch.exact_refs.get("eval") != request.eval_ref:
            raise PriceDispositionBlocked("PRICE_CASE_BATCH_POLICY_OR_EVAL_DRIFTED")
        eligible = {item.sku_ref.resource_id: item.sku_ref for item in batch.items if item.disposition is PriceBatchDisposition.ELIGIBLE}
        if any(eligible.get(ref.resource_id) != ref for ref in request.target_refs):
            raise PriceDispositionBlocked("PRICE_CASE_TARGET_NOT_ELIGIBLE_OR_DRIFTED")
        payload = request.model_dump(mode="json", by_alias=True)
        item = PriceCaseRevision(
            tenant=self._tenant(scope), **payload, contentHash=canonical_hash(payload),
            createdBy=actor, createdAt=at,
        )
        return self.store.append_case(scope, item)

    def create_contract(self, scope: TenantScope, request: CreatePriceDispositionContractRequest, actor: str, *, now: datetime | None = None) -> PriceDispositionContractRevision:
        at = now or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        full = {
            **payload,
            "requiredGateTypes": REQUIRED_GATE_TYPES[request.kind],
            "externalEffectCapable": request.kind in {PriceDispositionKind.EXTERNAL_NOTICE, PriceDispositionKind.REPRICING},
        }
        item = PriceDispositionContractRevision(
            tenant=self._tenant(scope), **full, contentHash=canonical_hash(full), createdBy=actor, createdAt=at,
        )
        return self.store.append_contract(scope, item)

    def prepare(self, scope: TenantScope, request: PreparePriceDispositionRequest, actor: str, *, now: datetime | None = None) -> PriceDispositionRevision:
        at = now or datetime.now(UTC)
        case = self.store.require_case(scope, request.case_ref)
        contract = self.store.require_contract(scope, request.contract_ref)
        case_targets = {ref.resource_id: ref for ref in case.target_refs}
        if any(case_targets.get(ref.resource_id) != ref for ref in request.target_refs):
            raise PriceDispositionBlocked("PRICE_DISPOSITION_TARGET_SCOPE_DRIFTED")
        if set(request.gate_refs) != set(contract.required_gate_types):
            raise PriceDispositionBlocked("PRICE_DISPOSITION_GATE_SET_DRIFTED")
        for key, resource_type in contract.required_gate_types.items():
            if request.gate_refs[key].resource_type != resource_type:
                raise PriceDispositionBlocked(f"PRICE_DISPOSITION_GATE_TYPE_DRIFTED:{key}")
        self.store.require_gate_authorities(scope, contract, request.gate_refs)
        payload = request.model_dump(mode="json", by_alias=True)
        binding_hash = canonical_hash({"case": request.case_ref, "contract": request.contract_ref, "targets": request.target_refs, "gates": request.gate_refs, "purpose": request.purpose, "requestedOutcome": request.requested_outcome})
        blockers = {
            PriceDispositionKind.INTERNAL_ADVICE: [],
            PriceDispositionKind.MODULE_HANDOFF: ["PRICE_HANDOFF_ISSUE_NOT_AUTHORIZED"],
            PriceDispositionKind.EXTERNAL_NOTICE: ["PRICE_NOTICE_OPERATIONAL_AUTHORITY_NOT_GRANTED"],
            PriceDispositionKind.REPRICING: ["PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED"],
        }[contract.kind]
        content_hash = canonical_hash({**payload, "kind": contract.kind, "bindingHash": binding_hash, "operationalBlockers": blockers})
        existing = self.store.latest_disposition_or_none(scope, request.disposition_id)
        if existing is not None:
            if existing.content_hash == content_hash:
                return existing
            raise PriceDispositionConflict("PRICE_DISPOSITION_IDEMPOTENCY_CONFLICT")
        item = PriceDispositionRevision(
            tenant=self._tenant(scope), dispositionId=request.disposition_id, revision=1, version=1, lifecycle="prepared",
            kind=contract.kind, caseRef=request.case_ref, contractRef=request.contract_ref, targetRefs=request.target_refs,
            gateRefs=request.gate_refs, purpose=request.purpose, requestedOutcome=request.requested_outcome,
            bindingHash=binding_hash, operationalBlockers=blockers, contentHash=content_hash,
            createdBy=actor, createdAt=at,
        )
        return self.store.append_disposition(scope, item)

    def freeze(self, scope: TenantScope, disposition_id: str, request: FreezePriceDispositionRequest, actor: str, *, now: datetime | None = None) -> PriceDispositionRevision:
        at = now or datetime.now(UTC)
        current = self.store.latest_disposition(scope, disposition_id)
        if current.lifecycle != "prepared" or current.version != request.expected_version or current.content_hash != request.expected_content_hash:
            raise PriceDispositionConflict("PRICE_DISPOSITION_EXPECTED_VERSION_OR_HASH_DRIFTED")
        expected_refs = {"case": current.case_ref, "contract": current.contract_ref, **current.gate_refs}
        if request.exact_refs != expected_refs:
            raise PriceDispositionConflict("PRICE_DISPOSITION_EXACT_REFS_DRIFTED")
        payload = current.model_dump(
            mode="json",
            by_alias=True,
            exclude={"revision", "version", "lifecycle", "prior_content_hash", "content_hash", "created_by", "created_at"},
        )
        content_hash = canonical_hash({**payload, "revision": current.revision + 1, "version": current.version + 1, "lifecycle": "frozen", "priorContentHash": current.content_hash})
        frozen = current.model_copy(update={
            "revision": current.revision + 1, "version": current.version + 1, "lifecycle": "frozen",
            "prior_content_hash": current.content_hash, "content_hash": content_hash, "created_by": actor, "created_at": at,
        })
        return self.store.append_disposition(scope, frozen)

    def record_observation(self, scope: TenantScope, request: RecordPriceDispositionObservationRequest) -> PriceDispositionObservation:
        disposition = self.store.require_disposition(scope, request.disposition_ref)
        if disposition.lifecycle != "frozen":
            raise PriceDispositionBlocked("PRICE_DISPOSITION_NOT_FROZEN")
        expected_receipt_type = {
            PriceDispositionKind.INTERNAL_ADVICE: "AdoptionReceipt",
            PriceDispositionKind.MODULE_HANDOFF: "HandoffDecisionRevision",
            PriceDispositionKind.EXTERNAL_NOTICE: "ActionReceipt",
            PriceDispositionKind.REPRICING: "ActionReceipt",
        }[disposition.kind]
        if request.receipt_ref.resource_type != expected_receipt_type:
            raise PriceDispositionBlocked("PRICE_DISPOSITION_RECEIPT_TYPE_DRIFTED")
        allowed_outcomes = {
            PriceDispositionKind.INTERNAL_ADVICE: {PriceDispositionOutcome.ADOPTED, PriceDispositionOutcome.REJECTED, PriceDispositionOutcome.UNKNOWN, PriceDispositionOutcome.DISPUTED},
            PriceDispositionKind.MODULE_HANDOFF: {PriceDispositionOutcome.ACCEPTED, PriceDispositionOutcome.REJECTED, PriceDispositionOutcome.UNKNOWN, PriceDispositionOutcome.DISPUTED},
            PriceDispositionKind.EXTERNAL_NOTICE: {PriceDispositionOutcome.APPLIED, PriceDispositionOutcome.FAILED, PriceDispositionOutcome.UNKNOWN, PriceDispositionOutcome.DISPUTED},
            PriceDispositionKind.REPRICING: {PriceDispositionOutcome.APPLIED, PriceDispositionOutcome.FAILED, PriceDispositionOutcome.UNKNOWN, PriceDispositionOutcome.DISPUTED},
        }[disposition.kind]
        if request.outcome not in allowed_outcomes:
            raise PriceDispositionBlocked("PRICE_DISPOSITION_OUTCOME_KIND_DRIFTED")
        self.store.require_outcome_receipt(scope, request.receipt_ref, disposition.binding_hash)
        payload = request.model_dump(mode="json", by_alias=True)
        item = PriceDispositionObservation(
            tenant=self._tenant(scope), observationId=f"price-disposition-observation-{canonical_hash(payload)[:24]}",
            **payload, contentHash=canonical_hash(payload),
        )
        return self.store.append_observation(scope, item)

    def contribution_view(self, scope: TenantScope, *, now: datetime | None = None) -> PriceDispositionContributionView:
        at = now or datetime.now(UTC)
        try:
            cases = self.store.list_cases(scope)
            dispositions = self.store.list_dispositions(scope)
            observations = self.store.list_observations(scope)
        except PriceDispositionBlocked as exc:
            if str(exc) != "PRICE_DISPOSITION_AUTHORITY_UNAVAILABLE":
                raise
            cases, dispositions, observations = [], [], []
            unavailable = True
        else:
            unavailable = False
        counts = {kind: sum(item.kind is kind for item in dispositions) for kind in PriceDispositionKind}
        blockers = ["PRICE_DISPOSITION_AUTHORITY_UNAVAILABLE"] if unavailable else []
        if not cases:
            blockers.append("PRICE_CASE_NOT_AVAILABLE")
        if not dispositions:
            blockers.append("PRICE_DISPOSITION_NOT_AVAILABLE")
        blockers.extend(["PRICE_NOTICE_OPERATIONAL_AUTHORITY_NOT_GRANTED", "PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED"])
        return PriceDispositionContributionView(
            tenant=self._tenant(scope), evaluatedAt=at, caseCount=len(cases), dispositionCounts=counts,
            latestDisposition=dispositions[-1] if dispositions else None,
            latestObservation=observations[-1] if observations else None, blockers=list(dict.fromkeys(blockers)),
        )


__all__ = [name for name in globals() if name.startswith("Price") or name.startswith("Create") or name.startswith("Prepare") or name.startswith("Freeze") or name.startswith("Record") or name in {"EcommerceWorkshopPriceDispositionService", "PRICE_DISPOSITION_SCHEMA_VERSION", "PRICE_DISPOSITION_SKILL_IDS"}]
