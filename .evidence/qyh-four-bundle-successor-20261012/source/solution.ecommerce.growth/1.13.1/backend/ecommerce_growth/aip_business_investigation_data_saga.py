"""N4 exact data-resume and unknown-result reconciliation commands."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping


def build_resume_data_command(
    *,
    occurrence_ref: Mapping[str, object],
    case_ref: Mapping[str, object],
    profile_ref: Mapping[str, object],
    cutoff_at: datetime,
    idempotency_key: str,
    prior_receipt_ref: Mapping[str, object],
    requirement_ref: Mapping[str, object],
    fulfillment_ref: Mapping[str, object],
    checkpoint_ref: Mapping[str, object],
    prior_plan_ref: Mapping[str, object],
    source_readiness_ref: Mapping[str, object],
    mapping_ref: Mapping[str, object],
    evidence_refs: tuple[Mapping[str, object], ...],
    observed_at: datetime,
) -> dict[str, object]:
    return {
        "operation": "runtime.analysis.resume_data",
        "occurrenceRef": dict(occurrence_ref),
        "caseRef": dict(case_ref),
        "profileRef": dict(profile_ref),
        "cutoffAt": cutoff_at.isoformat(),
        "idempotencyKey": idempotency_key,
        "priorReceiptRef": dict(prior_receipt_ref),
        "requirementRef": dict(requirement_ref),
        "fulfillmentRef": dict(fulfillment_ref),
        "checkpointRef": dict(checkpoint_ref),
        "priorPlanRef": dict(prior_plan_ref),
        "sourceReadinessRef": dict(source_readiness_ref),
        "mappingRef": dict(mapping_ref),
        "evidenceRefs": [dict(ref) for ref in evidence_refs],
        "observedAt": observed_at.isoformat(),
    }


def build_reconcile_command(
    *,
    occurrence_ref: Mapping[str, object],
    case_ref: Mapping[str, object],
    profile_ref: Mapping[str, object],
    cutoff_at: datetime,
    idempotency_key: str,
    prior_receipt_ref: Mapping[str, object],
    checkpoint_ref: Mapping[str, object] | None,
) -> dict[str, object]:
    return {
        "operation": "runtime.analysis.reconcile_unknown",
        "occurrenceRef": dict(occurrence_ref),
        "caseRef": dict(case_ref),
        "profileRef": dict(profile_ref),
        "cutoffAt": cutoff_at.isoformat(),
        "idempotencyKey": idempotency_key,
        "priorReceiptRef": dict(prior_receipt_ref),
        "requirementRef": None,
        "fulfillmentRef": None,
        "checkpointRef": None if checkpoint_ref is None else dict(checkpoint_ref),
    }


__all__ = ["build_reconcile_command", "build_resume_data_command"]
