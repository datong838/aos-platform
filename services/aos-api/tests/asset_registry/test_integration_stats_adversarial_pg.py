"""Adversarial PostgreSQL coverage for authorized Integration Case statistics."""

from __future__ import annotations

from datetime import datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_EVIDENCE_ADAPTER,
    CreateIntegrationCaseRequest,
    IntegrationEvidenceEnvelope,
)
from aos_api.asset_registry.integration_reader import PostgresIntegrationCaseReader
from aos_api.asset_registry.integration_store import PostgresIntegrationStore
from tests.asset_registry.test_integration_store_pg import (
    INSTALLATION_ID,
    ORG,
    PROJECT,
    ZERO_HASH,
    _Clock,
    _schema,
    _seed_active_installation,
)


def _create_case(
    store: PostgresIntegrationStore,
    *,
    display_name: str,
    required_markings: list[str],
):
    return store.create_current_case(
        org_id=ORG,
        project_id=PROJECT,
        request=CreateIntegrationCaseRequest.model_validate(
            {
                "installationId": str(INSTALLATION_ID),
                "overlayRevision": "overlay-v1",
                "displayName": display_name,
            }
        ),
        owner="owner:statistics-test",
        required_markings=required_markings,
    )


def _evidence(
    when: datetime,
    *,
    sequence: int,
    evidence_type: str,
    subject_ref: str,
    claims: dict[str, object],
) -> IntegrationEvidenceEnvelope:
    payload = {
        "evidenceId": f"55000000-0000-4000-8000-{sequence:012d}",
        "revision": 1,
        "evidenceType": evidence_type,
        "seriesKey": f"series:statistics:{sequence}",
        "subjectRef": subject_ref,
        "artifactRef": f"artifact:statistics:{sequence}",
        "artifactHash": ZERO_HASH,
        "outcome": "valid",
        "observedAt": when,
        "expiresAt": None,
        "revokedAt": None,
        "requiredMarkings": [],
        "producer": "producer:statistics-test",
        "claims": claims,
        "recordedAt": when,
    }
    hash_payload = dict(payload)
    timestamp = when.isoformat().replace("+00:00", "Z")
    hash_payload["observedAt"] = timestamp
    hash_payload["recordedAt"] = timestamp
    payload["evidenceHash"] = canonical_sha256(hash_payload)
    return INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)


def _source(when: datetime, *, sequence: int, subject_ref: str):
    return _evidence(
        when,
        sequence=sequence,
        evidence_type="source_connection",
        subject_ref=subject_ref,
        claims={
            "connectionRef": subject_ref,
            "authMode": "oauth",
            "readProbe": True,
            "tenantBinding": True,
        },
    )


def _pipeline(when: datetime, *, sequence: int, subject_ref: str):
    return _evidence(
        when,
        sequence=sequence,
        evidence_type="pipeline_run",
        subject_ref=subject_ref,
        claims={
            "pipelineRef": subject_ref,
            "runId": f"run:{sequence}",
            "result": "succeeded",
            "inputRevision": "input:1",
            "outputRevision": "output:1",
        },
    )


def _dataset(
    when: datetime,
    *,
    sequence: int,
    subject_ref: str,
    row_count: int,
):
    return _evidence(
        when,
        sequence=sequence,
        evidence_type="dataset_revision",
        subject_ref=subject_ref,
        claims={
            "datasetRef": subject_ref,
            "revision": "revision:1",
            "schemaHash": ZERO_HASH,
            "rowCount": row_count,
        },
    )


def _runtime(
    when: datetime,
    *,
    sequence: int,
    subject_ref: str,
    latency_ms: int,
):
    return _evidence(
        when,
        sequence=sequence,
        evidence_type="runtime_health",
        subject_ref=subject_ref,
        claims={
            "deploymentRef": subject_ref,
            "runId": f"run:health:{sequence}",
            "healthy": True,
            "latencyMs": latency_ms,
        },
    )


def _project(
    store: PostgresIntegrationStore,
    *,
    case_id: str,
    evidence: list[IntegrationEvidenceEnvelope],
) -> None:
    store.project_case(
        org_id=ORG,
        project_id=PROJECT,
        case_id=case_id,
        if_match_etag=1,
        evidence=evidence,
        cause="statistics_adversarial",
    )


def _assert_cutoff_is_unified(stats) -> None:
    metrics = (
        stats.case_count,
        stats.production_active_count,
        stats.connector_count,
        stats.pipeline_count,
        stats.dataset_row_count,
        stats.latency_ms,
    )
    assert len({metric.cutoff_at for metric in metrics}) == 1


def test_authorization_precedes_total_page_and_stats_with_stable_aggregation() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        clock = _Clock()
        store = PostgresIntegrationStore(connect_factory, clock=clock)
        internal = _create_case(
            store,
            display_name="Internal current",
            required_markings=["internal"],
        )
        secret = _create_case(
            store,
            display_name="Secret current",
            required_markings=["secret"],
        )
        empty = _create_case(
            store,
            display_name="Empty current",
            required_markings=["empty"],
        )
        reference = store.create_reference_case(
            org_id=ORG,
            project_id=PROJECT,
            display_name="Redacted reference",
            required_markings=["secret"],
        )

        clock.advance()
        _project(
            store,
            case_id=internal.case_id,
            evidence=[
                _source(clock.value, sequence=1, subject_ref="connector:shared"),
                _source(clock.value, sequence=2, subject_ref="connector:internal"),
                _pipeline(clock.value, sequence=3, subject_ref="pipeline:shared"),
                _pipeline(clock.value, sequence=4, subject_ref="pipeline:internal"),
                _dataset(
                    clock.value,
                    sequence=5,
                    subject_ref="dataset:shared",
                    row_count=0,
                ),
                _runtime(
                    clock.value,
                    sequence=6,
                    subject_ref="deployment:internal",
                    latency_ms=0,
                ),
            ],
        )
        clock.advance()
        _project(
            store,
            case_id=secret.case_id,
            evidence=[
                _source(clock.value, sequence=7, subject_ref="connector:shared"),
                _source(clock.value, sequence=8, subject_ref="connector:secret"),
                _pipeline(clock.value, sequence=9, subject_ref="pipeline:shared"),
                _pipeline(clock.value, sequence=10, subject_ref="pipeline:secret"),
                _dataset(
                    clock.value,
                    sequence=11,
                    subject_ref="dataset:shared",
                    row_count=0,
                ),
                _dataset(
                    clock.value,
                    sequence=12,
                    subject_ref="dataset:secret",
                    row_count=7,
                ),
                _runtime(
                    clock.value,
                    sequence=13,
                    subject_ref="deployment:secret",
                    latency_ms=41,
                ),
            ],
        )
        reader = PostgresIntegrationCaseReader(connect_factory)

        internal_only = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="current",
            allowed_markings=("internal",),
            limit=1,
            offset=0,
        )
        assert internal_only.total == 1
        assert [item.case_id for item in internal_only.items] == [internal.case_id]
        assert internal_only.stats is not None
        assert internal_only.stats.case_count.value == 1
        assert internal_only.stats.connector_count.value == 2
        assert internal_only.stats.pipeline_count.value == 2
        assert internal_only.stats.dataset_row_count.value == 0
        assert internal_only.stats.latency_ms.value == 0
        assert internal_only.stats.dataset_row_count.measured_case_count == 1
        assert internal_only.stats.dataset_row_count.eligible_case_count == 1
        _assert_cutoff_is_unified(internal_only.stats)

        empty_only = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="current",
            allowed_markings=("empty",),
            limit=20,
            offset=0,
        )
        assert empty_only.total == 1
        assert [item.case_id for item in empty_only.items] == [empty.case_id]
        assert empty_only.stats is not None
        assert empty_only.stats.connector_count.value is None
        assert empty_only.stats.pipeline_count.value is None
        assert empty_only.stats.dataset_row_count.value is None
        assert empty_only.stats.latency_ms.value is None
        assert empty_only.stats.latency_ms.measured_case_count == 0
        assert empty_only.stats.latency_ms.eligible_case_count == 1
        _assert_cutoff_is_unified(empty_only.stats)

        all_current = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="current",
            allowed_markings=("empty", "internal", "secret"),
            limit=1,
            offset=0,
        )
        assert all_current.total == 3
        assert len(all_current.items) == 1
        assert all_current.stats is not None
        assert all_current.stats.case_count.value == 3
        assert all_current.stats.connector_count.value == 3
        assert all_current.stats.pipeline_count.value == 3
        assert all_current.stats.dataset_row_count.value == 7
        assert all_current.stats.latency_ms.value == 41
        assert all_current.stats.connector_count.measured_case_count == 2
        assert all_current.stats.connector_count.eligible_case_count == 3
        _assert_cutoff_is_unified(all_current.stats)

        full_page = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="current",
            allowed_markings=("empty", "internal", "secret"),
            limit=20,
            offset=0,
        )
        expected_ids = [item.case_id for item in full_page.items]
        paged_ids = [
            reader.list_cases(
                org_id=ORG,
                project_id=PROJECT,
                scope="current",
                allowed_markings=("empty", "internal", "secret"),
                limit=1,
                offset=offset,
            )
            .items[0]
            .case_id
            for offset in range(3)
        ]
        repeated_ids = [
            item.case_id
            for item in reader.list_cases(
                org_id=ORG,
                project_id=PROJECT,
                scope="current",
                allowed_markings=("empty", "internal", "secret"),
                limit=20,
                offset=0,
            ).items
        ]
        assert paged_ids == expected_ids == repeated_ids
        assert reference.case_id not in expected_ids

        hidden_reference = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="reference",
            allowed_markings=("internal",),
            limit=20,
            offset=0,
        )
        assert hidden_reference.total == 0
        assert hidden_reference.items == []
        assert hidden_reference.stats is None

        visible_reference = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="reference",
            allowed_markings=("secret",),
            limit=20,
            offset=0,
        )
        assert visible_reference.total == 1
        assert [item.case_id for item in visible_reference.items] == [reference.case_id]
        assert visible_reference.stats is None
