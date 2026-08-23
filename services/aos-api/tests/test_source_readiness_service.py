"""XU2-R1: policy-backed SourceReadiness evaluation gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aos_api.source_readiness import (
    AtomicSourceFacts,
    ObservedQueryCapability,
    ObservedSourceFacts,
    SourceReadinessService,
)
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    LatestRunObservation,
    ObservationStatus,
    SourceCounts,
    SourceReadinessStatus,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


class Facts:
    def __init__(self, snapshot: AtomicSourceFacts) -> None:
        self.snapshot = snapshot

    def read_atomic(self, *, org_id: str, project_id: str) -> AtomicSourceFacts:
        assert (org_id, project_id) == ("org-org", "dev-project")
        return self.snapshot


def _snapshot(
    *,
    checked_at: datetime = NOW,
    query_status: str = "active",
    count_delta: int = 0,
) -> AtomicSourceFacts:
    sources = []
    for index, canonical in enumerate(CANONICAL_QYH_SOURCES):
        source_total = 1
        sources.append(
            ObservedSourceFacts(
                pipeline_id=canonical.pipeline_id,
                object_type=canonical.object_type,
                pipeline_present=True,
                source_present=True,
                source_id="niushop-qyh",
                target=f"ontology:{canonical.object_type}",
                schedule_id=f"sch-{canonical.pipeline_id}",
                cron=f"0 {index + 2} * * *",
                schedule_enabled=True,
                ingest_kind="pipeline-live-v1",
                ingest_pipeline_id=canonical.pipeline_id,
                ingest_source_id="niushop-qyh",
                latest_run=LatestRunObservation(
                    runId=f"run-{canonical.pipeline_id}",
                    status=ObservationStatus.SUCCEEDED,
                    scheduledFor=NOW,
                    startedAt=NOW,
                    finishedAt=NOW,
                    rowsWritten=1,
                ),
                source_event_at=NOW,
                counts=SourceCounts(
                    sourceTotal=source_total,
                    sourceActive=source_total,
                    sourceDeleted=0,
                    projectionTotal=source_total + count_delta,
                    unexplainedDelta=count_delta,
                ),
            )
        )
    return AtomicSourceFacts(
        checked_at=checked_at,
        sources=tuple(sources),
        query_capability=ObservedQueryCapability(
            binding_id="ecommerce.data_advisor.strategy.plan.r2",
            capability_id="strategy.plan",
            version=63,
            status=query_status,
            dependency_snapshot_hash="a" * 64,
        ),
    )


def test_twelve_sources_become_ready_with_exact_authority_and_same_snapshot() -> None:
    envelope = SourceReadinessService(Facts(_snapshot())).read(
        org_id="org-org", project_id="dev-project"
    )

    assert envelope.status == SourceReadinessStatus.READY
    assert len(envelope.sources) == 12
    assert all(item.status == SourceReadinessStatus.READY for item in envelope.sources)
    assert all(item.source_config_ref is not None for item in envelope.sources)
    assert all(item.query_capability_ref is not None for item in envelope.sources)
    assert all(item.blockers == [] for item in envelope.sources)
    assert all(item.data_cutoff == NOW for item in envelope.sources)


def test_missing_query_binding_fails_closed_without_fabricating_authority() -> None:
    envelope = SourceReadinessService(
        Facts(_snapshot(query_status="suspended"))
    ).read(org_id="org-org", project_id="dev-project")

    assert envelope.status == SourceReadinessStatus.BLOCKED
    assert all(item.query_capability_ref is None for item in envelope.sources)
    assert all(
        "QUERY_CAPABILITY_REF_MISSING" in item.blockers
        for item in envelope.sources
    )


def test_stale_and_reconciliation_failure_are_not_reported_ready() -> None:
    stale = SourceReadinessService(
        Facts(_snapshot(checked_at=NOW + timedelta(days=2)))
    ).read(org_id="org-org", project_id="dev-project")
    failed = SourceReadinessService(Facts(_snapshot(count_delta=1))).read(
        org_id="org-org", project_id="dev-project"
    )

    assert stale.status == SourceReadinessStatus.STALE
    assert all("SOURCE_DATA_STALE" in item.reasons for item in stale.sources)
    assert failed.status == SourceReadinessStatus.FAILED
    assert all(
        "SOURCE_RECONCILIATION_FAILED" in item.reasons
        for item in failed.sources
    )
