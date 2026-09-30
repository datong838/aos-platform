"""BG-03 single-product method draft; exact links are not factual authority.

The Host must resolve every reference, tenant, freshness and approval before
publishing or using this draft. This package contract performs no I/O or writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .sdk_ports import ExactRef


def _text(value: str, field: str, *, maximum: int = 2000) -> None:
    if (type(value) is not str or not 1 <= len(value) <= maximum
            or value != value.strip() or not value.isprintable()):
        raise ValueError(f"{field} requires bounded printable business text")


def _ref_payload(ref: ExactRef) -> dict[str, object]:
    return {"resourceType": ref.resource_type, "resourceId": ref.resource_id,
            "revision": ref.revision, "contentHash": ref.content_hash,
            **({"receiptId": ref.receipt_id} if ref.receipt_id is not None else {})}


@dataclass(frozen=True, slots=True)
class EvidenceBackedStatement:
    text: str
    evidence_refs: tuple[ExactRef, ...]

    def __post_init__(self) -> None:
        _text(self.text, "statement")
        if (type(self.evidence_refs) is not tuple or not 1 <= len(self.evidence_refs) <= 20
                or any(type(ref) is not ExactRef or ref.resource_type != "EvidenceBundleRevision"
                       for ref in self.evidence_refs)
                or len(set(self.evidence_refs)) != len(self.evidence_refs)):
            raise ValueError("statement needs unique exact evidence bundle references")

    def payload(self) -> dict[str, object]:
        return {"text": self.text, "evidenceRefs": [_ref_payload(ref) for ref in self.evidence_refs]}


@dataclass(frozen=True, slots=True)
class SalesWeaponBriefDraft:
    plan_ref: ExactRef
    decision_ref: ExactRef
    product_source_key: str
    product_label: str
    audience_hypothesis: EvidenceBackedStatement
    scenario: EvidenceBackedStatement
    fit_for: tuple[EvidenceBackedStatement, ...]
    not_fit_for: tuple[EvidenceBackedStatement, ...]
    proposed_value_claims: tuple[EvidenceBackedStatement, ...]
    unknown_facts: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    handoff_condition: str
    evidence_refs: tuple[ExactRef, ...]
    source_cutoff_at: datetime

    def __post_init__(self) -> None:
        if type(self.plan_ref) is not ExactRef or self.plan_ref.resource_type != "GrowthPlanRevision":
            raise ValueError("exact GrowthPlan reference required")
        if type(self.decision_ref) is not ExactRef or self.decision_ref.resource_type != "DecisionSummaryRevision":
            raise ValueError("exact decision reference required")
        _text(self.product_source_key, "product source key", maximum=240)
        _text(self.product_label, "product label", maximum=500)
        _text(self.handoff_condition, "handoff condition")
        if type(self.source_cutoff_at) is not datetime or self.source_cutoff_at.utcoffset() is None:
            raise ValueError("source cutoff must include timezone")
        if (type(self.evidence_refs) is not tuple or not 1 <= len(self.evidence_refs) <= 100
                or any(type(ref) is not ExactRef or ref.resource_type != "EvidenceBundleRevision"
                       for ref in self.evidence_refs)
                or len(set(self.evidence_refs)) != len(self.evidence_refs)):
            raise ValueError("unique draft evidence bundle references required")
        if type(self.audience_hypothesis) is not EvidenceBackedStatement or type(self.scenario) is not EvidenceBackedStatement:
            raise ValueError("sourced audience hypothesis and scenario required")
        statements = [self.audience_hypothesis, self.scenario]
        for field in (self.fit_for, self.not_fit_for, self.proposed_value_claims):
            if (type(field) is not tuple or not 1 <= len(field) <= 20
                    or any(type(item) is not EvidenceBackedStatement for item in field)):
                raise ValueError("bounded sourced fit, exclusion and proposed value required")
            statements.extend(field)
        if len({item.text for item in statements}) != len(statements):
            raise ValueError("duplicate business statement")
        allowed = set(self.evidence_refs)
        if any(not set(item.evidence_refs).issubset(allowed) for item in statements):
            raise ValueError("statement references evidence outside the draft")
        for name, values in (("unknown facts", self.unknown_facts),
                             ("prohibited claims", self.prohibited_claims)):
            if type(values) is not tuple or not 1 <= len(values) <= 30 or len(set(values)) != len(values):
                raise ValueError(f"{name} must be bounded and unique")
            for value in values:
                _text(value, name)

    def validate_against(self, plan_ref: ExactRef, decision_ref: ExactRef,
                         allowed_evidence_refs: tuple[ExactRef, ...], *, observed_at: datetime) -> None:
        """Compare supplied exact refs only; Host still resolves current authority."""
        if (type(plan_ref) is not ExactRef or type(decision_ref) is not ExactRef
                or plan_ref != self.plan_ref or decision_ref != self.decision_ref
                or type(allowed_evidence_refs) is not tuple
                or not set(self.evidence_refs).issubset(set(allowed_evidence_refs))
                or type(observed_at) is not datetime or observed_at.utcoffset() is None
                or self.source_cutoff_at > observed_at):
            raise ValueError("draft differs from current supplied exact context")

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": "aos.ecommerce.sales-weapon-brief-draft/v1",
            "authority": "draft-only",
            "planRef": _ref_payload(self.plan_ref), "decisionRef": _ref_payload(self.decision_ref),
            "productSourceKey": self.product_source_key, "productLabel": self.product_label,
            "audienceHypothesis": self.audience_hypothesis.payload(),
            "scenario": self.scenario.payload(),
            "fitFor": [item.payload() for item in self.fit_for],
            "notFitFor": [item.payload() for item in self.not_fit_for],
            "proposedValueClaims": [item.payload() for item in self.proposed_value_claims],
            "unknownFacts": list(self.unknown_facts), "prohibitedClaims": list(self.prohibited_claims),
            "handoffCondition": self.handoff_condition,
            "evidenceRefs": [_ref_payload(ref) for ref in self.evidence_refs],
            "sourceCutoffAt": self.source_cutoff_at.isoformat(),
        }
