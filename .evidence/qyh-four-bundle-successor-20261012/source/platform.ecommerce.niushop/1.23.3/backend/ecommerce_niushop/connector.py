"""Bounded Niushop fact query and observation validation."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Any, Mapping, Self

from pydantic import Field, field_validator, model_validator

from .business_investigation_niushop_profile import NIUSHOP_SEMANTIC_FAMILIES
from .sdk_ports import (
    AdapterContract,
    ConnectorPort,
    ConnectorRequest,
    DispatchRef,
    ExactRef,
    request_connector,
)


READ_OPERATION = "ecommerce_niushop_facts_read"


def connector_operation_schema() -> dict[str, Any]:
    """Signed runtime declaration consumed by the generic host broker at activation."""
    return {
        "operationId": READ_OPERATION,
        "parameters": [
            {
                "name": "requirementRef", "kind": "exact_ref",
                "resourceType": "DataRequirementRevision",
            },
            {
                "name": "sourceReadinessRef", "kind": "exact_ref",
                "resourceType": "SourceReadinessEnvelope", "receiptRequired": True,
            },
            {
                "name": "mappingRef", "kind": "exact_ref",
                "resourceType": "SourceMappingRevision",
            },
            {"name": "factFamilies", "kind": "string_list", "minimum": 1, "maximum": 16},
            {
                "name": "objectIds", "kind": "string_list", "required": False,
                "minimum": 0, "maximum": 200,
            },
            {"name": "selectedFields", "kind": "string_list", "minimum": 1, "maximum": 100},
            {"name": "maxRows", "kind": "integer", "minimum": 1, "maximum": 1000},
            {"name": "timeoutSeconds", "kind": "integer", "minimum": 1, "maximum": 30},
        ],
    }


class NiushopFactQuery(AdapterContract):
    requirement_ref: ExactRef
    connection_ref: ExactRef
    source_readiness_ref: ExactRef
    mapping_ref: ExactRef
    cutoff_at: datetime
    fact_families: list[str] = Field(min_length=1, max_length=16)
    object_ids: list[str] = Field(default_factory=list, max_length=200)
    selected_fields: list[str] = Field(min_length=1, max_length=100)
    max_rows: int = Field(ge=1, le=1000)
    timeout_seconds: int = Field(ge=1, le=30)
    idempotency_key: str = Field(min_length=1, max_length=200)

    @field_validator("cutoff_at")
    @classmethod
    def _aware_cutoff(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("cutoffAt must include timezone")
        return value

    @field_validator("fact_families", "object_ids", "selected_fields")
    @classmethod
    def _unique_non_blank(cls, value: list[str], info) -> list[str]:
        if any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError(f"{info.field_name} must be unique and non-blank")
        return value

    @model_validator(mode="after")
    def _exact_authority(self) -> Self:
        expected = {
            "requirement_ref": "DataRequirementRevision",
            "connection_ref": "ConnectionRevision",
            "source_readiness_ref": "SourceReadinessEnvelope",
            "mapping_ref": "SourceMappingRevision",
        }
        for name, resource_type in expected.items():
            ref = getattr(self, name)
            if ref.resource_type != resource_type:
                raise ValueError(f"{name} must reference {resource_type}")
        if self.source_readiness_ref.receipt_id is None:
            raise ValueError("sourceReadinessRef requires receiptId")
        if not set(self.fact_families) <= NIUSHOP_SEMANTIC_FAMILIES:
            raise ValueError("query contains an unknown Niushop fact family")
        return self


class NiushopFact(AdapterContract):
    fact_id: str = Field(min_length=1, max_length=240)
    fact_family: str = Field(min_length=1, max_length=120)
    canonical_type: str = Field(min_length=1, max_length=120)
    object_id: str = Field(min_length=1, max_length=240)
    field: str = Field(min_length=1, max_length=120)
    value: str | int | float | bool | None
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def _aware_as_of(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("fact asOf must include timezone")
        return value

    @field_validator("value")
    @classmethod
    def _finite_value(cls, value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("fact numeric value must be finite")
        return value


class NiushopObservationBatch(AdapterContract):
    requirement_ref: ExactRef
    source_readiness_ref: ExactRef
    mapping_ref: ExactRef
    cutoff_at: datetime
    observed_at: datetime
    facts: list[NiushopFact] = Field(min_length=1, max_length=1000)
    fact_refs: list[ExactRef] = Field(min_length=1, max_length=1000)
    evidence_refs: list[ExactRef] = Field(min_length=1, max_length=200)
    quality_score: float = Field(ge=0, le=1)
    source_summary_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("cutoff_at", "observed_at")
    @classmethod
    def _aware_times(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observation times must include timezone")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.observed_at < self.cutoff_at or self.observed_at - self.cutoff_at > timedelta(hours=24):
            raise ValueError("observation must be produced within 24 hours of cutoff")
        if any(item.as_of != self.cutoff_at for item in self.facts):
            raise ValueError("every fact must use the exact requirement cutoff")
        for ref in self.fact_refs:
            if ref.resource_type != "FactRevision":
                raise ValueError("factRefs must reference FactRevision")
        for ref in self.evidence_refs:
            if ref.resource_type not in {"EvidenceBundleRevision", "DatasetRevision"}:
                raise ValueError("evidenceRefs must reference canonical evidence")
        identities = [
            (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            for ref in [*self.fact_refs, *self.evidence_refs]
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("observation references must be unique")
        fact_ids = [item.fact_id for item in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("fact IDs must be unique")
        if (
            {ref.resource_id for ref in self.fact_refs} != set(fact_ids)
            or len(self.fact_refs) != len(fact_ids)
        ):
            raise ValueError("every fact must have one exact FactRevision ref")
        return self


def read_bounded_facts(
    query: NiushopFactQuery,
    *,
    dispatch_ref: DispatchRef,
    port: ConnectorPort,
) -> NiushopObservationBatch:
    request = ConnectorRequest(
        connection_ref=query.connection_ref.model_dump(by_alias=True, exclude_none=True),
        operation_id=READ_OPERATION,
        typed_params={
            "requirementRef": query.requirement_ref.model_dump(
                by_alias=True, exclude_none=True
            ),
            "sourceReadinessRef": query.source_readiness_ref.model_dump(
                by_alias=True, exclude_none=True
            ),
            "mappingRef": query.mapping_ref.model_dump(by_alias=True, exclude_none=True),
            "factFamilies": list(query.fact_families),
            "objectIds": list(query.object_ids),
            "selectedFields": list(query.selected_fields),
            "maxRows": query.max_rows,
            "timeoutSeconds": query.timeout_seconds,
        },
        cutoff_at=query.cutoff_at,
        idempotency_key=query.idempotency_key,
    )
    raw = request_connector(port, dispatch_ref, request)
    if not isinstance(raw, Mapping):
        raise ValueError("connector returned no observation object")
    result = NiushopObservationBatch.model_validate(raw)
    if (
        result.requirement_ref != query.requirement_ref
        or result.source_readiness_ref != query.source_readiness_ref
        or result.mapping_ref != query.mapping_ref
        or result.cutoff_at != query.cutoff_at
        or result.quality_score <= 0
    ):
        raise ValueError("connector observation drifted from the exact query authority")
    if not {item.fact_family for item in result.facts} <= set(query.fact_families):
        raise ValueError("connector returned an unrequested fact family")
    if len(result.facts) > query.max_rows:
        raise ValueError("connector returned more facts than maxRows")
    if not {item.field for item in result.facts} <= set(query.selected_fields):
        raise ValueError("connector returned an unrequested field")
    if query.object_ids and not {item.object_id for item in result.facts} <= set(
        query.object_ids
    ):
        raise ValueError("connector returned an unrequested object")
    return result


__all__ = [
    "NiushopFact", "NiushopFactQuery", "NiushopObservationBatch", "READ_OPERATION",
    "connector_operation_schema", "read_bounded_facts",
]
