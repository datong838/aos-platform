"""W2-00B: Workshop consumes canonical SourceReadiness fail closed."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_source_readiness import (
    EcommerceWorkshopSourceReadiness,
    SourceReadinessTenantMismatchError,
)
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    SourceReadinessEnvelope,
)


NOW = datetime(2026, 8, 21, 14, tzinfo=UTC)
BLOCKERS = [
    "SOURCE_CONFIG_EXACT_REF_MISSING",
    "FRESHNESS_POLICY_REF_MISSING",
    "QUALITY_POLICY_REF_MISSING",
    "RECONCILIATION_POLICY_REF_MISSING",
    "QUERY_CAPABILITY_REF_MISSING",
]


def _envelope(*, status: str, org_id: str = "org-org") -> SourceReadinessEnvelope:
    return SourceReadinessEnvelope.model_validate(
        {
            "tenant": {"orgId": org_id, "projectId": "dev-project"},
            "checkedAt": NOW,
            "cutoffAt": NOW,
            "status": status,
            "sources": [
                {
                    "tenant": {"orgId": org_id, "projectId": "dev-project"},
                    "sourceId": "niushop-qyh",
                    "pipelineId": source.pipeline_id,
                    "objectType": source.object_type,
                    "status": status,
                    "checkedAt": NOW,
                    "reasons": BLOCKERS,
                    "blockers": BLOCKERS,
                }
                for source in CANONICAL_QYH_SOURCES
            ],
        }
    )


class FakeReader:
    def __init__(self, envelope: SourceReadinessEnvelope) -> None:
        self.envelope = envelope
        self.calls: list[tuple[str, str]] = []

    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope:
        self.calls.append((org_id, project_id))
        return self.envelope


@pytest.mark.parametrize("status", ["blocked", "stale", "unknown"])
def test_facade_preserves_canonical_fail_closed_status(status: str) -> None:
    canonical = _envelope(status=status)
    reader = FakeReader(canonical)

    actual = EcommerceWorkshopSourceReadiness(reader).read(
        org_id="org-org",
        project_id="dev-project",
    )

    assert actual is canonical
    assert actual.status.value == status
    assert len(actual.sources) == 12
    assert all(source.blockers == BLOCKERS for source in actual.sources)
    assert reader.calls == [("org-org", "dev-project")]


def test_facade_rejects_cross_tenant_envelope() -> None:
    reader = FakeReader(_envelope(status="blocked", org_id="dev-org"))

    with pytest.raises(SourceReadinessTenantMismatchError):
        EcommerceWorkshopSourceReadiness(reader).read(
            org_id="org-org",
            project_id="dev-project",
        )

    assert reader.calls == [("org-org", "dev-project")]


def test_facade_has_no_persistence_or_pipeline_query_surface() -> None:
    source = inspect.getsource(EcommerceWorkshopSourceReadiness).lower()
    for forbidden in (
        "select ",
        "insert ",
        "update ",
        "delete ",
        "meta_pipeline",
        "ecom_object",
    ):
        assert forbidden not in source
