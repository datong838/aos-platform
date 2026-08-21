"""W-L19 EffectReview / EffectMaturity accepted≠completed axes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_effect_review import (
    CreateEffectReviewRequest,
    EffectMaturityStatus,
    EvaluateEffectMaturityRequest,
)
from aos_api.aip_effect_review_store import (
    AipEffectReviewConflict,
    AipEffectReviewStore,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)


def _subject() -> str:
    return f"effect-subj-{uuid4().hex[:10]}"


def _ref(resource_id: str) -> ResourceRef:
    return ResourceRef(
        resource_type="aos.task_run",
        resource_id=resource_id,
        revision="1",
        authority="aos.task",
    )


def test_accept_does_not_complete_when_immature() -> None:
    store = AipEffectReviewStore()
    subject = _subject()
    cutoff = NOW + timedelta(days=7)
    review = store.create_review(
        SCOPE,
        CreateEffectReviewRequest(
            subject_id=subject,
            subject_ref=_ref(subject),
            sample_count=10,
            min_sample=5,
            cutoff_at=cutoff,
            event_time_at=NOW,
            accepted=True,
            expected_revision=0,
        ),
        "tester",
        now=NOW,
    )
    assert review.accepted is True
    assert review.maturity_status is EffectMaturityStatus.IMMATURE
    assert review.effect_completed is False

    decision = store.evaluate_maturity(
        SCOPE,
        EvaluateEffectMaturityRequest(subject_id=subject, observed_at=NOW),
        "tester",
        now=NOW,
    )
    assert decision.accepted is True
    assert decision.maturity_status is EffectMaturityStatus.IMMATURE
    assert decision.effect_completed is False


def test_cas_conflict_and_five_axis_projection() -> None:
    store = AipEffectReviewStore()
    subject = _subject()
    store.create_review(
        SCOPE,
        CreateEffectReviewRequest(
            subject_id=subject,
            subject_ref=_ref(subject),
            sample_count=0,
            min_sample=3,
            cutoff_at=NOW,
            event_time_at=NOW - timedelta(hours=1),
            accepted=False,
            expected_revision=0,
        ),
        "tester",
        now=NOW,
    )
    with pytest.raises(AipEffectReviewConflict):
        store.create_review(
            SCOPE,
            CreateEffectReviewRequest(
                subject_id=subject,
                subject_ref=_ref(subject),
                sample_count=3,
                min_sample=3,
                cutoff_at=NOW,
                event_time_at=NOW - timedelta(hours=1),
                accepted=True,
                expected_revision=0,
            ),
            "tester",
            now=NOW,
        )
    mature = store.create_review(
        SCOPE,
        CreateEffectReviewRequest(
            subject_id=subject,
            subject_ref=_ref(subject),
            sample_count=5,
            min_sample=3,
            cutoff_at=NOW,
            event_time_at=NOW - timedelta(hours=1),
            accepted=False,
            expected_revision=1,
        ),
        "tester",
        now=NOW,
    )
    assert mature.revision == 2
    assert mature.maturity_status is EffectMaturityStatus.MATURE
    assert mature.accepted is False
    assert mature.effect_completed is True

    axes = store.get_axis_snapshot(SCOPE, subject)
    assert axes.effect_maturity is EffectMaturityStatus.MATURE
    assert axes.accepted is False
    assert axes.effect_completed is True
    assert axes.usage_settlement in {"has_receipts", "no_receipts"}
    assert axes.review_revision == 2
