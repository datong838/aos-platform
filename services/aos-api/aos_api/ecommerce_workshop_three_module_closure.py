"""W6-09 canonical closure bridge for creator, price and customer modules.

The bridge never accepts caller-declared aggregate success.  Item outcomes,
usage, effect maturity and handoff decisions are resolved from their existing
tenant authorities and remain five independent axes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.tenant_scope import TenantScope


THREE_MODULE_CLOSURE_SCHEMA_VERSION = "aos.ecommerce-workshop.three-module-closure/v1"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ThreeModuleClosureBlocked(RuntimeError):
    code = "THREE_MODULE_CLOSURE_BLOCKED"


class ThreeModuleClosureConflict(ThreeModuleClosureBlocked):
    code = "THREE_MODULE_CLOSURE_CONFLICT"


class ThreeModule(StrEnum):
    CREATOR = "creator"
    PRICE = "price"
    CUSTOMER = "customer"


class CanonicalItemOutcome(StrEnum):
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"
    SKIPPED = "skipped"


class ClosureState(StrEnum):
    EMPTY = "empty"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ClosureExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=240)


class CompileThreeModuleClosureRequest(AipContractModel):
    module: ThreeModule
    source_ref: ClosureExactRef

    @model_validator(mode="after")
    def _source_type(self) -> "CompileThreeModuleClosureRequest":
        expected = {
            ThreeModule.CREATOR: "CreatorBatchStartDecisionRevision",
            ThreeModule.PRICE: "PriceDispositionRevision",
            ThreeModule.CUSTOMER: "CustomerBatchStartDecisionRevision",
        }
        if self.source_ref.resource_type != expected[self.module]:
            raise ValueError("three-module sourceRef type drifted")
        return self


class ThreeModuleItemOutcome(AipContractModel):
    item_key: str = Field(min_length=1, max_length=240)
    original_status: str = Field(min_length=1, max_length=80)
    canonical_outcome: CanonicalItemOutcome
    original_ref: ClosureExactRef
    receipt_ref: ClosureExactRef | None = None


class ThreeModuleClosureLedger(AipContractModel):
    total: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    unknown: int = Field(ge=0)
    disputed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    state: ClosureState

    @model_validator(mode="after")
    def _conserved(self) -> "ThreeModuleClosureLedger":
        values = [self.in_progress, self.succeeded, self.failed, self.unknown, self.disputed, self.skipped]
        if self.total != sum(values):
            raise ValueError("three-module closure ledger must conserve items")
        nonzero = sum(value > 0 for value in values)
        expected = (
            ClosureState.EMPTY if self.total == 0 else
            ClosureState.COMPLETED if self.succeeded == self.total else
            ClosureState.FAILED if self.failed == self.total else
            ClosureState.UNKNOWN if self.unknown == self.total else
            ClosureState.IN_PROGRESS if self.in_progress == self.total else
            ClosureState.PARTIAL if nonzero > 1 else
            ClosureState.PARTIAL
        )
        if self.state is not expected:
            raise ValueError("three-module closure state does not match item algebra")
        return self


class ThreeModuleClosureRevision(AipContractModel):
    tenant: TenantContext
    closure_id: str
    revision: int = 1
    module: ThreeModule
    source_ref: ClosureExactRef
    items: list[ThreeModuleItemOutcome] = Field(default_factory=list, max_length=2000)
    ledger: ThreeModuleClosureLedger
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    compiled_by: str
    compiled_at: datetime


class BindThreeModuleUsageRequest(AipContractModel):
    closure_ref: ClosureExactRef
    usage_receipt_id: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _closure(self) -> "BindThreeModuleUsageRequest":
        if self.closure_ref.resource_type != "ThreeModuleClosureRevision":
            raise ValueError("closureRef drifted")
        return self


class ThreeModuleUsageBindingRevision(AipContractModel):
    tenant: TenantContext
    binding_id: str
    revision: int = 1
    closure_ref: ClosureExactRef
    usage_receipt_ref: ClosureExactRef
    lineage_id: str
    quality: str = Field(pattern=r"^(measured|estimated|unknown)$")
    quantity: float | None = Field(default=None, ge=0)
    unit: str
    adjustment_total: float = 0
    settlement: str = Field(pattern=r"^(measured|estimated|unknown)$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bound_at: datetime

    @model_validator(mode="after")
    def _unknown_has_no_quantity(self) -> "ThreeModuleUsageBindingRevision":
        if self.quality == "unknown" and self.quantity is not None:
            raise ValueError("unknown usage cannot invent zero or quantity")
        if self.quality != "unknown" and self.quantity is None:
            raise ValueError("known usage requires canonical quantity")
        return self


class BindThreeModuleEffectRequest(AipContractModel):
    closure_ref: ClosureExactRef
    effect_review_id: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _closure(self) -> "BindThreeModuleEffectRequest":
        if self.closure_ref.resource_type != "ThreeModuleClosureRevision":
            raise ValueError("closureRef drifted")
        return self


class ThreeModuleEffectBindingRevision(AipContractModel):
    tenant: TenantContext
    binding_id: str
    revision: int = 1
    closure_ref: ClosureExactRef
    effect_review_ref: ClosureExactRef
    maturity_status: str = Field(pattern=r"^(immature|mature|insufficient|unknown)$")
    accepted: bool
    effect_completed: bool
    sample_count: int = Field(ge=0)
    min_sample: int = Field(ge=1)
    cutoff_at: datetime
    observed_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bound_at: datetime

    @model_validator(mode="after")
    def _maturity_is_honest(self) -> "ThreeModuleEffectBindingRevision":
        if self.effect_completed != (self.maturity_status == "mature"):
            raise ValueError("effectCompleted must follow canonical maturity only")
        return self


class BindThreeModuleHandoffRequest(AipContractModel):
    closure_ref: ClosureExactRef
    handoff_id: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _closure(self) -> "BindThreeModuleHandoffRequest":
        if self.closure_ref.resource_type != "ThreeModuleClosureRevision":
            raise ValueError("closureRef drifted")
        return self


class ThreeModuleHandoffBindingRevision(AipContractModel):
    tenant: TenantContext
    binding_id: str
    revision: int = 1
    closure_ref: ClosureExactRef
    handoff_ref: ClosureExactRef
    transport_status: str
    business_decision: str | None = Field(default=None, pattern=r"^(accepted|rejected|request_more|returned)$")
    task_ref: dict[str, Any]
    task_run_ref: dict[str, Any]
    disclosure_ref_count: int = Field(ge=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bound_at: datetime


class ThreeModuleClosureContributionView(AipContractModel):
    schema_version: str = THREE_MODULE_CLOSURE_SCHEMA_VERSION
    tenant: TenantContext
    module: ThreeModule
    evaluated_at: datetime
    atomic_skill_ids: list[str]
    logic_id: str
    primary_colleague: str
    collaborator_colleagues: list[str]
    latest_closure: ThreeModuleClosureRevision | None
    latest_usage: ThreeModuleUsageBindingRevision | None
    latest_effect: ThreeModuleEffectBindingRevision | None
    latest_handoff: ThreeModuleHandoffBindingRevision | None
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: [
        "COMPILE_THREE_MODULE_CLOSURE",
        "BIND_CANONICAL_USAGE",
        "BIND_CANONICAL_EFFECT_REVIEW",
        "BIND_CANONICAL_HANDOFF",
    ])
    handoff_consume_allowed: bool = False
    memory_promotion_allowed: bool = False
    external_effects_allowed: bool = False


_CONTRIBUTION = {
    ThreeModule.CREATOR: (
        ["creator-batch-prepare", "creator-lane-reconcile", "creator-relationship-review"],
        "ecommerce-creator-growth",
        "达人运营官",
        ["内容官", "数据参谋"],
    ),
    ThreeModule.PRICE: (
        ["compile-price-case", "prepare-price-handoff", "evaluate-price-effect"],
        "ecommerce-price-governance",
        "数据参谋",
        ["活动策划师", "导购顾问"],
    ),
    ThreeModule.CUSTOMER: (
        ["segment-customers", "design-customer-journey", "evaluate-dialogue-effect"],
        "ecommerce-customer-relationship",
        "私域管家",
        ["内容官", "客服专员", "导购顾问", "数据参谋"],
    ),
}


def _ledger(items: list[ThreeModuleItemOutcome]) -> ThreeModuleClosureLedger:
    counts = {value.value: 0 for value in CanonicalItemOutcome}
    for item in items:
        counts[item.canonical_outcome.value] += 1
    total = len(items)
    nonzero = sum(value > 0 for value in counts.values())
    state = (
        ClosureState.EMPTY if total == 0 else
        ClosureState.COMPLETED if counts["succeeded"] == total else
        ClosureState.FAILED if counts["failed"] == total else
        ClosureState.UNKNOWN if counts["unknown"] == total else
        ClosureState.IN_PROGRESS if counts["in_progress"] == total else
        ClosureState.PARTIAL if nonzero > 1 else
        ClosureState.PARTIAL
    )
    return ThreeModuleClosureLedger(total=total, state=state, **counts)


class EcommerceWorkshopThreeModuleClosureService:
    def __init__(self, store: Any) -> None:
        self.store = store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _ref(resource_type: str, resource_id: str, content_hash: str) -> ClosureExactRef:
        return ClosureExactRef(
            resourceType=resource_type,
            resourceId=resource_id,
            revision=1,
            contentHash=f"sha256:{content_hash}",
            receiptId=f"receipt-{resource_id}",
        )

    def compile(self, scope: TenantScope, request: CompileThreeModuleClosureRequest, actor: str, *, now: datetime | None = None) -> ThreeModuleClosureRevision:
        at = now or datetime.now(UTC)
        items = self.store.resolve_domain_items(scope, request.module, request.source_ref)
        payload = {"module": request.module, "sourceRef": request.source_ref, "items": items}
        content_hash = canonical_hash(payload)
        closure_id = f"three-module-closure-{canonical_hash([*scope.key, request.module, request.source_ref.resource_id])[:24]}"
        item = ThreeModuleClosureRevision(
            tenant=self._tenant(scope), closureId=closure_id, module=request.module,
            sourceRef=request.source_ref, items=items, ledger=_ledger(items),
            contentHash=content_hash, compiledBy=actor, compiledAt=at,
        )
        return self.store.append_closure(scope, item)

    def require_closure(self, scope: TenantScope, ref: ClosureExactRef) -> ThreeModuleClosureRevision:
        return self.store.require_closure(scope, ref)

    def bind_usage(self, scope: TenantScope, request: BindThreeModuleUsageRequest, *, now: datetime | None = None) -> ThreeModuleUsageBindingRevision:
        at = now or datetime.now(UTC)
        self.store.require_closure(scope, request.closure_ref)
        resolved = self.store.resolve_usage(scope, request.usage_receipt_id)
        payload = {"closureRef": request.closure_ref, **resolved}
        content_hash = canonical_hash(payload)
        item = ThreeModuleUsageBindingRevision(
            tenant=self._tenant(scope), bindingId=f"three-module-usage-{content_hash[:24]}",
            closureRef=request.closure_ref, contentHash=content_hash, boundAt=at, **resolved,
        )
        return self.store.append_usage_binding(scope, item)

    def bind_effect(self, scope: TenantScope, request: BindThreeModuleEffectRequest, *, now: datetime | None = None) -> ThreeModuleEffectBindingRevision:
        at = now or datetime.now(UTC)
        closure = self.store.require_closure(scope, request.closure_ref)
        resolved = self.store.resolve_effect(scope, request.effect_review_id, closure.source_ref)
        payload = {"closureRef": request.closure_ref, **resolved}
        content_hash = canonical_hash(payload)
        item = ThreeModuleEffectBindingRevision(
            tenant=self._tenant(scope), bindingId=f"three-module-effect-{content_hash[:24]}",
            closureRef=request.closure_ref, contentHash=content_hash, boundAt=at, **resolved,
        )
        return self.store.append_effect_binding(scope, item)

    def bind_handoff(self, scope: TenantScope, request: BindThreeModuleHandoffRequest, *, now: datetime | None = None) -> ThreeModuleHandoffBindingRevision:
        at = now or datetime.now(UTC)
        self.store.require_closure(scope, request.closure_ref)
        resolved = self.store.resolve_handoff(scope, request.handoff_id)
        payload = {"closureRef": request.closure_ref, **resolved}
        content_hash = canonical_hash(payload)
        item = ThreeModuleHandoffBindingRevision(
            tenant=self._tenant(scope), bindingId=f"three-module-handoff-{content_hash[:24]}",
            closureRef=request.closure_ref, contentHash=content_hash, boundAt=at, **resolved,
        )
        return self.store.append_handoff_binding(scope, item)

    def contribution_view(self, scope: TenantScope, module: ThreeModule, *, now: datetime | None = None) -> ThreeModuleClosureContributionView:
        at = now or datetime.now(UTC)
        latest = self.store.latest_bindings(scope, module)
        skills, logic, primary, collaborators = _CONTRIBUTION[module]
        closure = latest["closure"]
        blockers: list[str] = []
        if closure is None:
            blockers.append("THREE_MODULE_CLOSURE_NOT_COMPILED")
        if latest["usage"] is None:
            blockers.append("THREE_MODULE_USAGE_NOT_BOUND")
        if latest["effect"] is None:
            blockers.append("THREE_MODULE_EFFECT_NOT_BOUND")
        elif latest["effect"].maturity_status != "mature":
            blockers.append(f"THREE_MODULE_EFFECT_{latest['effect'].maturity_status.upper()}")
        if latest["handoff"] is None:
            blockers.append("THREE_MODULE_HANDOFF_NOT_BOUND")
        return ThreeModuleClosureContributionView(
            tenant=self._tenant(scope), module=module, evaluatedAt=at,
            atomicSkillIds=skills, logicId=logic, primaryColleague=primary,
            collaboratorColleagues=collaborators, latestClosure=closure,
            latestUsage=latest["usage"], latestEffect=latest["effect"],
            latestHandoff=latest["handoff"], blockers=blockers,
        )


__all__ = [name for name in globals() if name.startswith("ThreeModule") or name.startswith("BindThree") or name.startswith("CompileThree") or name == "EcommerceWorkshopThreeModuleClosureService"]
