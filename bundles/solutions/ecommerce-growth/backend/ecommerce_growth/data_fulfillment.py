"""Growth-side DataRequirement/Fulfillment composition through a public host port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Any, Mapping

from aos_extension_sdk import DispatchRef, commit_with_dispatch

from .sdk_ports import ExactRef, GrowthDataPort


FULFILL_OPERATION = "ecommerce_growth_data_fulfill"


def _authorize_dispatch(dispatch_ref: DispatchRef) -> None:
    if dispatch_ref.handler_kind != "extension" or dispatch_ref.operation_id != FULFILL_OPERATION:
        raise PermissionError("dispatch does not authorize ecommerce data fulfillment")


@dataclass(frozen=True, slots=True)
class DataRequirementSpec:
    case_ref: ExactRef
    run_ref: ExactRef
    checkpoint_ref: ExactRef
    channel_ref: ExactRef
    entity_ref: ExactRef
    required_facts: tuple[str, ...]
    window_start: datetime
    window_end: datetime
    cutoff_at: datetime
    quality_threshold: float
    min_population: int
    idempotency_key: str

    def __post_init__(self) -> None:
        expected = (
            (self.case_ref, "BusinessInvestigationCaseRevision"),
            (self.run_ref, "BusinessInvestigationRun"),
            (self.checkpoint_ref, "CheckpointRevision"),
            (self.channel_ref, "ChannelRevision"),
            (self.entity_ref, "BusinessEntityRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("data requirement contains an invalid exact reference")
        if any(value.utcoffset() is None for value in (self.window_start, self.window_end, self.cutoff_at)):
            raise ValueError("data requirement times must include timezone")
        if not self.window_start < self.window_end <= self.cutoff_at:
            raise ValueError("data requirement window must end at or before cutoff")
        if (
            not self.required_facts
            or any(not value.strip() for value in self.required_facts)
            or len(self.required_facts) != len(set(self.required_facts))
        ):
            raise ValueError("required facts must be unique and non-empty")
        if not 0 <= self.quality_threshold <= 1 or self.min_population <= 0:
            raise ValueError("invalid data quality threshold")
        if not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("invalid data requirement idempotency key")


def _ref_payload(ref: ExactRef) -> dict[str, Any]:
    return {
        "resourceType": ref.resource_type,
        "resourceId": ref.resource_id,
        "revision": ref.revision,
        "contentHash": ref.content_hash,
        **({"receiptId": ref.receipt_id} if ref.receipt_id is not None else {}),
    }


def _exact_ref(payload: Mapping[str, Any], expected: set[str]) -> ExactRef:
    allowed = {"resourceType", "resourceId", "revision", "contentHash", "receiptId"}
    required = allowed - {"receiptId"}
    if set(payload) - allowed or not required <= set(payload):
        raise ValueError("host returned a non-exact reference")
    ref = ExactRef(
        str(payload["resourceType"]), str(payload["resourceId"]), int(payload["revision"]),
        str(payload["contentHash"]),
        None if payload.get("receiptId") is None else str(payload["receiptId"]),
    )
    if ref.resource_type not in expected:
        raise ValueError("host returned an unexpected exact reference")
    return ref


def request_requirement(
    port: GrowthDataPort,
    dispatch_ref: DispatchRef,
    spec: DataRequirementSpec,
) -> ExactRef:
    _authorize_dispatch(dispatch_ref)
    command = {
        "operation": "data.requirement.request",
        "idempotencyKey": spec.idempotency_key,
        "caseRef": _ref_payload(spec.case_ref),
        "runRef": _ref_payload(spec.run_ref),
        "checkpointRef": _ref_payload(spec.checkpoint_ref),
        "channelRef": _ref_payload(spec.channel_ref),
        "entityRef": _ref_payload(spec.entity_ref),
        "requiredFacts": list(spec.required_facts),
        "timeWindow": {"startAt": spec.window_start.isoformat(), "endAt": spec.window_end.isoformat()},
        "cutoffAt": spec.cutoff_at.isoformat(),
        "qualityThreshold": spec.quality_threshold,
        "minPopulation": spec.min_population,
    }
    result = commit_with_dispatch(port, dispatch_ref, command)
    if not isinstance(result, Mapping) or not isinstance(result.get("requirementRef"), Mapping):
        raise ValueError("Data port returned no requirement Receipt")
    return _exact_ref(result["requirementRef"], {"DataRequirementRevision"})


def bind_observation_fulfillment(
    port: GrowthDataPort,
    dispatch_ref: DispatchRef,
    *,
    requirement_ref: ExactRef,
    cutoff_at: datetime,
    observation: Mapping[str, Any],
    idempotency_key: str,
) -> ExactRef:
    _authorize_dispatch(dispatch_ref)
    if requirement_ref.resource_type != "DataRequirementRevision" or cutoff_at.utcoffset() is None:
        raise ValueError("fulfillment requires an exact requirement and cutoff")
    if not 1 <= len(idempotency_key.strip()) <= 200:
        raise ValueError("fulfillment requires a valid idempotency key")
    if observation.get("cutoffAt") != cutoff_at.isoformat():
        raise ValueError("observation cutoff does not match the requirement")
    source_readiness = observation.get("sourceReadinessRef")
    evidence_refs = observation.get("evidenceRefs")
    fact_refs = observation.get("factRefs")
    if not isinstance(source_readiness, Mapping) or not isinstance(evidence_refs, list) or not evidence_refs:
        raise ValueError("observation lacks source readiness or evidence")
    if not isinstance(fact_refs, list) or not fact_refs:
        raise ValueError("observation lacks exact facts")
    readiness_ref = _exact_ref(source_readiness, {"SourceReadinessEnvelope"})
    if readiness_ref.receipt_id is None:
        raise ValueError("source readiness requires its exact Receipt")
    for ref in evidence_refs:
        _exact_ref(ref, {"EvidenceBundleRevision", "DatasetRevision"})
    for ref in fact_refs:
        _exact_ref(ref, {"FactRevision"})
    quality_score = observation.get("qualityScore")
    source_summary_hash = observation.get("sourceSummaryHash")
    if (
        type(quality_score) not in {int, float}
        or not math.isfinite(float(quality_score))
        or not 0 < float(quality_score) <= 1
        or type(source_summary_hash) is not str
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", source_summary_hash)
    ):
        raise ValueError("observation quality evidence is invalid")
    command = {
        "operation": "data.fulfillment.bind",
        "idempotencyKey": idempotency_key,
        "requirementRef": _ref_payload(requirement_ref),
        "sourceReadinessRef": dict(source_readiness),
        "artifactRefs": [*evidence_refs],
        "factRefs": [*fact_refs],
        "cutoffAt": cutoff_at.isoformat(),
        "qualityScore": quality_score,
        "sourceSummaryHash": source_summary_hash,
    }
    result = commit_with_dispatch(port, dispatch_ref, command)
    if not isinstance(result, Mapping) or not isinstance(result.get("fulfillmentRef"), Mapping):
        raise ValueError("Data port returned no fulfillment Receipt")
    return _exact_ref(result["fulfillmentRef"], {"DataFulfillmentReceipt"})


__all__ = [
    "DataRequirementSpec", "FULFILL_OPERATION", "bind_observation_fulfillment",
    "request_requirement",
]
