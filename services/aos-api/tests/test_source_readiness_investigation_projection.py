from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    InvestigationReadinessProjection,
    SourceReadinessEnvelope,
    SourceReadinessStatus,
)
from tests.test_source_readiness_contracts import _item

NOW = datetime(2026, 8, 26, 5, 30, tzinfo=UTC)


def requirement_ref():
    return {"resourceType": "DataRequirementRevision", "resourceId": "requirement-1", "revision": "1", "contentHash": "a" * 64, "authority": "data-requirement"}


def projection(**changes):
    value = {
        "requirementRef": requirement_ref(), "status": "ready", "evaluatedAt": NOW,
        "requiredCutoff": NOW, "freshnessExpiresAt": NOW + timedelta(hours=1),
        "requiredFactCount": 2, "coveredFactCount": 2, "coverageRatio": 1,
        "unmetFacts": [], "blockers": [],
    }
    value.update(changes); return value


def envelope(*, status=SourceReadinessStatus.READY, investigation=None):
    items = [_item(i, status=status) for i in range(len(CANONICAL_QYH_SOURCES))]
    items = [item.model_copy(update={"checked_at": NOW, "data_cutoff": NOW, "freshness_expires_at": NOW + timedelta(hours=1)}) for item in items]
    return SourceReadinessEnvelope(tenant={"orgId": "org-org", "projectId": "dev-project"}, checkedAt=NOW, cutoffAt=NOW, status=status, sources=items, investigation=investigation)


def test_optional_projection_preserves_old_v1_and_accepts_exact_full_coverage() -> None:
    assert envelope().investigation is None
    parsed = envelope(investigation=projection())
    assert parsed.investigation and parsed.investigation.coverage_ratio == 1


def test_projection_rejects_coverage_cutoff_and_raw_field_drift() -> None:
    with pytest.raises(ValidationError, match="coverageRatio"):
        InvestigationReadinessProjection.model_validate(projection(coveredFactCount=1, coverageRatio=1, unmetFacts=["Order"]))
    with pytest.raises(ValidationError, match="unmetFacts"):
        InvestigationReadinessProjection.model_validate(projection(coveredFactCount=1, coverageRatio=.5))
    with pytest.raises(ValidationError, match="requiredCutoff"):
        envelope(investigation=projection(requiredCutoff=NOW + timedelta(seconds=1)))
    with pytest.raises(ValidationError, match="Extra inputs"):
        InvestigationReadinessProjection.model_validate({**projection(), "rawPayload": {"secret": "forbidden"}})


def test_historical_success_cannot_override_current_failure() -> None:
    with pytest.raises(ValidationError, match="historical investigation success"):
        envelope(status=SourceReadinessStatus.FAILED, investigation=projection())
    blocked = projection(status="blocked", coveredFactCount=1, coverageRatio=.5, unmetFacts=["Order"], freshnessExpiresAt=None, blockers=[{"code": "SOURCE_STALE", "fact": "Order", "sourceIds": ["P05-order-qyh"], "reason": "current cutoff is stale"}])
    parsed = envelope(status=SourceReadinessStatus.FAILED, investigation=blocked)
    assert parsed.investigation and parsed.investigation.status == SourceReadinessStatus.BLOCKED
