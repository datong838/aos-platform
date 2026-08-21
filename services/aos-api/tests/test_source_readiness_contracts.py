"""XU1: canonical SourceReadiness contract gates."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    ExactResourceRef,
    LatestRunObservation,
    ObservationStatus,
    PolicyCheckStatus,
    PolicyObservation,
    SourceReadinessEnvelope,
    SourceReadinessItem,
    SourceReadinessStatus,
    aggregate_source_readiness_status,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _ref(kind: str, key: str) -> ExactResourceRef:
    return ExactResourceRef(
        resourceType=kind,
        resourceId=key,
        revision="revision-1",
        contentHash="a" * 64,
        authority="data-adapter",
    )


def _item(index: int, *, status: SourceReadinessStatus) -> SourceReadinessItem:
    source = CANONICAL_QYH_SOURCES[index]
    return SourceReadinessItem(
        tenant={"orgId": "org-org", "projectId": "dev-project"},
        sourceId="niushop-qyh",
        pipelineId=source.pipeline_id,
        objectType=source.object_type,
        status=status,
        checkedAt=NOW,
        dataCutoff=NOW,
        freshnessExpiresAt=NOW,
        sourceConfigRef=_ref("SourceConfig", "niushop-qyh"),
        mappingRef=_ref("Mapping", source.pipeline_id),
        schemaRef=_ref("SchemaFingerprint", "niushop-schema"),
        maskingPolicyRef=_ref("MaskingPolicy", "qyh-pii-exclusion"),
        freshnessPolicyRef=_ref("FreshnessPolicy", source.pipeline_id),
        qualityPolicyRef=_ref("QualityPolicy", source.pipeline_id),
        reconciliationPolicyRef=_ref("ReconciliationPolicy", source.pipeline_id),
        queryCapabilityRef=_ref("CapabilityBinding", source.object_type),
        latestRun=LatestRunObservation(status=ObservationStatus.SUCCEEDED),
        quality=PolicyObservation(status=PolicyCheckStatus.PASS),
        reconciliation=PolicyObservation(status=PolicyCheckStatus.PASS),
        reasons=[] if status == SourceReadinessStatus.READY else ["QUALITY_POLICY_REF_MISSING"],
        blockers=[] if status == SourceReadinessStatus.READY else ["QUALITY_POLICY_REF_MISSING"],
    )


def test_envelope_requires_exactly_twelve_unique_canonical_sources() -> None:
    items = [_item(index, status=SourceReadinessStatus.READY) for index in range(12)]
    envelope = SourceReadinessEnvelope(
        tenant={"orgId": "org-org", "projectId": "dev-project"},
        checkedAt=NOW,
        cutoffAt=NOW,
        status="ready",
        sources=items,
    )
    assert len(envelope.sources) == 12
    assert envelope.model_dump(by_alias=True)["tenant"] == {
        "orgId": "org-org",
        "projectId": "dev-project",
    }

    items[-1] = items[0]
    with pytest.raises(ValidationError, match="canonical P01-P12"):
        SourceReadinessEnvelope(
            tenant={"orgId": "org-org", "projectId": "dev-project"},
            checkedAt=NOW,
            cutoffAt=NOW,
            status="ready",
            sources=items,
        )


def test_status_precedence_fails_closed() -> None:
    assert aggregate_source_readiness_status(
        [SourceReadinessStatus.READY, SourceReadinessStatus.STALE]
    ) == SourceReadinessStatus.STALE
    assert aggregate_source_readiness_status(
        [SourceReadinessStatus.FAILED, SourceReadinessStatus.BLOCKED]
    ) == SourceReadinessStatus.BLOCKED


def test_contract_rejects_raw_or_secret_payload_fields() -> None:
    payload = _item(7, status=SourceReadinessStatus.BLOCKED).model_dump(by_alias=True)
    payload["rawPayload"] = {"mobile": "13800000000"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourceReadinessItem.model_validate(payload)
