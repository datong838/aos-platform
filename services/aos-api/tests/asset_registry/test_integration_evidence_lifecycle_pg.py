"""Real PostgreSQL proof for the complete M4 Evidence lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import EvidenceReferenceInvalidError
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_EVIDENCE_ADAPTER,
    EvidenceType,
    IntegrationEvidenceEnvelope,
)
from aos_api.asset_registry.integration_projection import IntegrationExpiryProjector
from aos_api.asset_registry.integration_service import (
    TrustedEvidenceWriter,
    TrustedProducerContext,
)
from aos_api.asset_registry.integration_store import PostgresIntegrationStore
from tests.asset_registry.test_integration_store_pg import (
    ORG,
    PROJECT,
    _create,
    _schema,
    _seed_active_installation,
)

ZERO_HASH = "sha256:" + "0" * 64
PRODUCER = "producer:m4-lifecycle"

CLAIMS: dict[str, dict[str, Any]] = {
    "source_connection": {
        "connectionRef": "connector:weixin",
        "authMode": "oauth",
        "readProbe": True,
        "tenantBinding": True,
    },
    "tenant_isolation": {
        "positiveTenant": "tenant:current",
        "negativeTenant": "tenant:other",
        "crossTenantDenied": True,
    },
    "pipeline_run": {
        "pipelineRef": "pipeline:orders",
        "runId": "run:1",
        "result": "succeeded",
        "inputRevision": "input:1",
        "outputRevision": "output:1",
    },
    "dataset_revision": {
        "datasetRef": "dataset:orders",
        "revision": "dataset-revision:1",
        "schemaHash": ZERO_HASH,
        "rowCount": 100,
    },
    "data_quality": {
        "datasetRef": "dataset:orders",
        "checkSetHash": ZERO_HASH,
        "requiredPassed": True,
        "failedChecks": [],
    },
    "ontology_revision": {
        "ontologyRef": "ontology:commerce",
        "revision": "ontology-revision:1",
        "schemaHash": ZERO_HASH,
    },
    "mapping_validation": {
        "mappingRef": "mapping:orders",
        "coverage": 1.0,
        "linkValidationPassed": True,
    },
    "logic_publication": {
        "logicRef": "logic:operations",
        "immutableRevision": "logic-revision:1",
        "publicationHash": ZERO_HASH,
    },
    "logic_eval": {
        "logicRef": "logic:operations",
        "evalSuiteHash": ZERO_HASH,
        "requiredPassed": True,
    },
    "workshop_validation": {
        "workshopRef": "workshop:operations",
        "realSource": True,
        "emptyStatePassed": True,
        "permissionPassed": True,
        "mainFlowPassed": True,
    },
    "action_safety": {
        "actionRef": "action:installation",
        "approvalControlPassed": True,
        "rollbackControlPassed": True,
        "idempotencyControlPassed": True,
        "installationApplyVerified": True,
        "installationVerifyVerified": True,
    },
    "operations_readiness": {
        "runbookRef": "runbook:commerce",
        "alertRef": "alert:commerce",
        "ownerRef": "owner:operations",
        "requiredChecksPassed": True,
    },
    "security_validation": {
        "policySetHash": ZERO_HASH,
        "requiredChecksPassed": True,
    },
    "runtime_health": {
        "deploymentRef": "deployment:commerce",
        "runId": "runtime:1",
        "healthy": True,
        "latencyMs": 25,
    },
}

STAGE_AFTER_WRITE = (
    "planned",
    "connection_verified",
    "connection_verified",
    "connection_verified",
    "data_verified",
    "data_verified",
    "ontology_verified",
    "ontology_verified",
    "logic_verified",
    "workshop_verified",
    "workshop_verified",
    "workshop_verified",
    "production_ready",
    "production_active",
)


@dataclass(slots=True)
class _Clock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@dataclass(frozen=True, slots=True)
class _DatabaseState:
    instance_revision: int
    etag_version: int
    snapshot_revision: int
    computed_stage: str
    snapshot_revisions: tuple[int, ...]
    event_rows: tuple[tuple[int, int, str | None, str, str], ...]
    evidence_count: int
    source_tail_revision: int | None
    snapshot_json: dict[str, Any]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _evidence(
    evidence_type: str,
    *,
    revision: int,
    outcome: str,
    observed_at: datetime,
    recorded_at: datetime,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> IntegrationEvidenceEnvelope:
    evidence_id = uuid.uuid5(uuid.NAMESPACE_URL, f"aos:m4:{evidence_type}")
    payload = {
        "evidenceId": str(evidence_id),
        "revision": revision,
        "evidenceType": evidence_type,
        "seriesKey": f"series:{evidence_type}",
        "subjectRef": f"subject:{evidence_type}",
        "artifactRef": f"artifact:{evidence_type}",
        "artifactHash": ZERO_HASH,
        "outcome": outcome,
        "observedAt": observed_at,
        "expiresAt": expires_at,
        "revokedAt": revoked_at,
        "requiredMarkings": ["internal"],
        "producer": PRODUCER,
        "claims": CLAIMS[evidence_type],
        "recordedAt": recorded_at,
    }
    hash_payload = {
        **payload,
        "observedAt": _iso(observed_at),
        "expiresAt": _iso(expires_at) if expires_at else None,
        "revokedAt": _iso(revoked_at) if revoked_at else None,
        "recordedAt": _iso(recorded_at),
    }
    payload["evidenceHash"] = canonical_sha256(hash_payload)
    return INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)


def _database_state(connect_factory, case_pk: uuid.UUID) -> _DatabaseState:
    with connect_factory() as conn:
        projection = conn.execute(
            """
            SELECT i.current_revision,i.etag_version,p.snapshot_revision,
                   p.computed_stage,s.snapshot_json
              FROM integration_instance AS i
              JOIN integration_case_projection AS p
                ON p.org_id=i.org_id AND p.project_id=i.project_id
               AND p.case_pk=i.case_pk
              JOIN integration_evidence_snapshot AS s
                ON s.org_id=p.org_id AND s.project_id=p.project_id
               AND s.case_pk=p.case_pk
               AND s.snapshot_revision=p.snapshot_revision
             WHERE i.org_id=%s AND i.project_id=%s AND i.case_pk=%s
            """,
            (ORG, PROJECT, case_pk),
        ).fetchone()
        snapshots = conn.execute(
            """SELECT snapshot_revision
                 FROM integration_evidence_snapshot
                WHERE org_id=%s AND project_id=%s AND case_pk=%s
                ORDER BY snapshot_revision""",
            (ORG, PROJECT, case_pk),
        ).fetchall()
        events = conn.execute(
            """SELECT sequence,snapshot_revision,old_stage,new_stage,cause
                 FROM integration_stage_event
                WHERE org_id=%s AND project_id=%s AND case_pk=%s
                ORDER BY sequence""",
            (ORG, PROJECT, case_pk),
        ).fetchall()
        evidence = conn.execute(
            """SELECT COUNT(*) AS evidence_count,
                      MAX(revision) FILTER (
                        WHERE evidence_type='source_connection'
                      ) AS source_tail_revision
                 FROM integration_evidence
                WHERE org_id=%s AND project_id=%s AND case_pk=%s""",
            (ORG, PROJECT, case_pk),
        ).fetchone()
    return _DatabaseState(
        instance_revision=projection["current_revision"],
        etag_version=projection["etag_version"],
        snapshot_revision=projection["snapshot_revision"],
        computed_stage=projection["computed_stage"],
        snapshot_revisions=tuple(row["snapshot_revision"] for row in snapshots),
        event_rows=tuple(
            (
                row["sequence"],
                row["snapshot_revision"],
                row["old_stage"],
                row["new_stage"],
                row["cause"],
            )
            for row in events
        ),
        evidence_count=evidence["evidence_count"],
        source_tail_revision=evidence["source_tail_revision"],
        snapshot_json=projection["snapshot_json"],
    )


def _assert_consistent(
    state: _DatabaseState,
    *,
    revision: int,
    stage: str,
    event_count: int,
    evidence_count: int,
) -> None:
    assert (
        state.instance_revision
        == state.etag_version
        == state.snapshot_revision
        == revision
    )
    assert state.computed_stage == stage
    assert state.snapshot_revisions == tuple(range(1, revision + 1))
    assert len(state.event_rows) == event_count
    assert state.evidence_count == evidence_count
    assert state.snapshot_json["snapshotRevision"] == revision
    assert state.snapshot_json["instanceRevision"] == revision
    assert state.snapshot_json["computedStage"] == stage


def test_trusted_evidence_lifecycle_is_atomic_and_projection_consistent() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        with connect_factory() as conn:
            database_now = conn.execute("SELECT clock_timestamp() AS now").fetchone()[
                "now"
            ]

        clock = _Clock(database_now - timedelta(seconds=40))
        store = PostgresIntegrationStore(connect_factory, clock=clock)
        created = _create(store)
        writer = TrustedEvidenceWriter(
            store=store,
            context=TrustedProducerContext(
                org_id=ORG,
                project_id=PROJECT,
                producer=PRODUCER,
                markings=("internal",),
                evidence_types=tuple(EvidenceType),
            ),
        )
        case_id = created.case_id
        observed_at = database_now - timedelta(seconds=60)
        expected_events = 1
        previous_stage = "planned"

        _assert_consistent(
            _database_state(connect_factory, created.case_pk),
            revision=1,
            stage="planned",
            event_count=1,
            evidence_count=0,
        )

        for index, (evidence_type, expected_stage) in enumerate(
            zip(CLAIMS, STAGE_AFTER_WRITE, strict=True), start=1
        ):
            clock.value += timedelta(seconds=1)
            projected = writer.write(
                case_id=case_id,
                evidence=_evidence(
                    evidence_type,
                    revision=1,
                    outcome="valid",
                    observed_at=observed_at,
                    recorded_at=clock.value,
                ),
            )
            revision = index + 1
            assert projected.response.snapshot_revision == revision
            assert projected.response.instance_revision == revision
            assert projected.response.etag_version == revision
            assert projected.response.computed_stage.value == expected_stage
            if expected_stage == previous_stage:
                assert projected.stage_event is None
            else:
                expected_events += 1
                assert projected.stage_event is not None
                assert projected.stage_event.sequence == expected_events
                assert projected.stage_event.snapshot_revision == revision
                assert projected.stage_event.old_stage.value == previous_stage
                assert projected.stage_event.new_stage.value == expected_stage
                assert projected.stage_event.cause == "evidence_added"
            previous_stage = expected_stage
            _assert_consistent(
                _database_state(connect_factory, created.case_pk),
                revision=revision,
                stage=expected_stage,
                event_count=expected_events,
                evidence_count=index,
            )

        assert expected_events == 8
        state = _database_state(connect_factory, created.case_pk)
        assert [row[4] for row in state.event_rows] == [
            "created",
            *("evidence_added" for _ in range(7)),
        ]

        clock.value = database_now - timedelta(seconds=10)
        negative = writer.write(
            case_id=case_id,
            evidence=_evidence(
                "source_connection",
                revision=2,
                outcome="invalid",
                observed_at=observed_at,
                recorded_at=clock.value,
            ),
        )
        assert negative.response.computed_stage.value == "planned"
        assert negative.stage_event is not None
        assert negative.stage_event.cause == "negative_observed"
        assert negative.stage_event.snapshot_revision == 16
        _assert_consistent(
            _database_state(connect_factory, created.case_pk),
            revision=16,
            stage="planned",
            event_count=9,
            evidence_count=15,
        )

        clock.value = database_now - timedelta(seconds=5)
        renewal = writer.write(
            case_id=case_id,
            evidence=_evidence(
                "source_connection",
                revision=3,
                outcome="valid",
                observed_at=observed_at,
                recorded_at=clock.value,
                expires_at=database_now - timedelta(seconds=1),
            ),
        )
        assert renewal.response.computed_stage.value == "production_active"
        assert renewal.stage_event is not None
        assert renewal.stage_event.cause == "evidence_added"
        assert renewal.stage_event.snapshot_revision == 17
        _assert_consistent(
            _database_state(connect_factory, created.case_pk),
            revision=17,
            stage="production_active",
            event_count=10,
            evidence_count=16,
        )

        projector = IntegrationExpiryProjector(connect_factory)
        expired = projector.refresh_case_if_due(
            org_id=ORG,
            project_id=PROJECT,
            case_id=case_id,
        )
        assert expired.projected is True
        assert expired.stage_changed is True
        assert expired.snapshot_revision == 18
        assert expired.etag_version == 18
        assert expired.computed_stage.value == "planned"
        state_after_expiry = _database_state(connect_factory, created.case_pk)
        _assert_consistent(
            state_after_expiry,
            revision=18,
            stage="planned",
            event_count=11,
            evidence_count=16,
        )
        assert state_after_expiry.event_rows[-1][4] == "evidence_expired"

        repeated = projector.refresh_case_if_due(
            org_id=ORG,
            project_id=PROJECT,
            case_id=case_id,
        )
        assert repeated.projected is False
        assert repeated.stage_changed is False
        assert repeated.snapshot_revision == 18
        assert repeated.etag_version == 18
        assert _database_state(connect_factory, created.case_pk) == state_after_expiry

        clock.value = expired.cutoff_at + timedelta(seconds=1)
        post_expiry_renewal = writer.write(
            case_id=case_id,
            evidence=_evidence(
                "source_connection",
                revision=4,
                outcome="valid",
                observed_at=observed_at,
                recorded_at=clock.value,
            ),
        )
        assert post_expiry_renewal.response.computed_stage.value == "production_active"
        assert post_expiry_renewal.stage_event is not None
        assert post_expiry_renewal.stage_event.cause == "evidence_added"
        _assert_consistent(
            _database_state(connect_factory, created.case_pk),
            revision=19,
            stage="production_active",
            event_count=12,
            evidence_count=17,
        )

        clock.value += timedelta(seconds=1)
        revoked = writer.write(
            case_id=case_id,
            evidence=_evidence(
                "source_connection",
                revision=5,
                outcome="revoked",
                observed_at=observed_at,
                recorded_at=clock.value,
                revoked_at=clock.value,
            ),
        )
        assert revoked.response.computed_stage.value == "planned"
        assert revoked.stage_event is not None
        assert revoked.stage_event.cause == "evidence_revoked"
        final_state = _database_state(connect_factory, created.case_pk)
        _assert_consistent(
            final_state,
            revision=20,
            stage="planned",
            event_count=13,
            evidence_count=18,
        )
        assert final_state.source_tail_revision == 5

        clock.value += timedelta(seconds=1)
        with pytest.raises(EvidenceReferenceInvalidError):
            writer.write(
                case_id=case_id,
                evidence=_evidence(
                    "source_connection",
                    revision=7,
                    outcome="valid",
                    observed_at=observed_at,
                    recorded_at=clock.value,
                ),
            )
        assert _database_state(connect_factory, created.case_pk) == final_state
