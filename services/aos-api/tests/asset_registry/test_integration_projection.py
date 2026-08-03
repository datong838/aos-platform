"""Real PostgreSQL coverage for M4 expiry projection and policy parity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_EVIDENCE_ADAPTER,
    IntegrationEvidenceEnvelope,
)
from aos_api.asset_registry.integration_projection import IntegrationExpiryProjector
from aos_api.asset_registry.integration_store import PostgresIntegrationStore
from psycopg.types.json import Jsonb
from tests.asset_registry.test_integration_store_pg import (
    ORG,
    PROJECT,
    _create,
    _schema,
    _seed_active_installation,
)

ZERO_HASH = "sha256:" + "0" * 64


@dataclass(slots=True)
class _Clock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


def _db_now(connect_factory) -> datetime:
    with connect_factory() as conn:
        return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def _evidence(
    *,
    evidence_type: str,
    evidence_id: str,
    revision: int,
    outcome: str,
    observed_at: datetime,
    recorded_at: datetime,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> IntegrationEvidenceEnvelope:
    claims = (
        {
            "connectionRef": "connector:weixin",
            "authMode": "oauth",
            "readProbe": True,
            "tenantBinding": True,
        }
        if evidence_type == "source_connection"
        else {
            "positiveTenant": "tenant:positive",
            "negativeTenant": "tenant:negative",
            "crossTenantDenied": True,
        }
    )
    series_key = "source" if evidence_type == "source_connection" else "tenant"
    payload = {
        "evidenceId": evidence_id,
        "revision": revision,
        "evidenceType": evidence_type,
        "seriesKey": series_key,
        "subjectRef": f"subject:{series_key}",
        "artifactRef": f"artifact:{series_key}",
        "artifactHash": ZERO_HASH,
        "outcome": outcome,
        "observedAt": observed_at,
        "expiresAt": expires_at,
        "revokedAt": revoked_at,
        "requiredMarkings": [],
        "producer": "producer:projection-test",
        "claims": claims,
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


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _seed_connection_verified_case(
    connect_factory,
    *,
    source_id: str | None = None,
    tenant_id: str | None = None,
    source_expiry: datetime | None = None,
    source_expiry_offset: timedelta | None = None,
):
    now = _db_now(connect_factory)
    if source_expiry_offset is not None:
        source_expiry = now + source_expiry_offset
    clock = _Clock(now - timedelta(seconds=10))
    store = PostgresIntegrationStore(connect_factory, clock=clock)
    created = _create(store)
    observed_at = now - timedelta(seconds=8)
    source = _evidence(
        evidence_type="source_connection",
        evidence_id=source_id or str(uuid.uuid4()),
        revision=1,
        outcome="valid",
        observed_at=observed_at,
        recorded_at=observed_at,
        expires_at=source_expiry,
    )
    tenant = _evidence(
        evidence_type="tenant_isolation",
        evidence_id=tenant_id or str(uuid.uuid4()),
        revision=1,
        outcome="valid",
        observed_at=observed_at,
        recorded_at=observed_at,
    )
    store.append_evidence(
        org_id=ORG, project_id=PROJECT, case_id=created.case_id, evidence=source
    )
    store.append_evidence(
        org_id=ORG, project_id=PROJECT, case_id=created.case_id, evidence=tenant
    )
    clock.value = now - timedelta(seconds=2)
    projected = store.project_case(
        org_id=ORG,
        project_id=PROJECT,
        case_id=created.case_id,
        if_match_etag=1,
        cause="evidence_added",
    )
    assert projected.response.computed_stage.value == "connection_verified"
    return store, clock, created, source, now


def _assert_python_pg_stage_match(connect_factory, case_pk: uuid.UUID) -> None:
    with connect_factory() as conn:
        row = conn.execute(
            """
            SELECT snapshot_json,cutoff_at,computed_stage
              FROM integration_evidence_snapshot
             WHERE org_id=%s AND project_id=%s AND case_pk=%s
             ORDER BY snapshot_revision DESC LIMIT 1
            """,
            (ORG, PROJECT, case_pk),
        ).fetchone()
        pg_stage = conn.execute(
            "SELECT integration_snapshot_computed_stage(%s::JSONB,%s) AS stage",
            (Jsonb(row["snapshot_json"]), row["cutoff_at"]),
        ).fetchone()["stage"]
    assert pg_stage == row["computed_stage"]


def test_read_refresh_uses_one_db_cutoff_and_is_repeatable_without_writes() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        expiry = _db_now(connect_factory) - timedelta(seconds=1)
        _, _, created, _, _ = _seed_connection_verified_case(
            connect_factory, source_expiry=expiry
        )
        projector = IntegrationExpiryProjector(connect_factory)

        refreshed = projector.refresh_case_if_due(
            org_id=ORG, project_id=PROJECT, case_id=created.case_id
        )

        assert refreshed.projected and refreshed.stage_changed
        assert refreshed.computed_stage.value == "planned"
        with connect_factory() as conn:
            mirrors = conn.execute(
                """
                SELECT p.cutoff_at,p.updated_at,s.cutoff_at AS snapshot_cutoff,
                       r.created_at AS revision_created,p.next_projection_at,
                       p.snapshot_revision,p.etag_version,
                       (SELECT COUNT(*) FROM integration_stage_event
                         WHERE org_id=%s AND project_id=%s AND case_pk=%s) AS events
                  FROM integration_case_projection AS p
                  JOIN integration_evidence_snapshot AS s
                    ON s.org_id=p.org_id AND s.project_id=p.project_id
                   AND s.case_pk=p.case_pk
                   AND s.snapshot_revision=p.snapshot_revision
                  JOIN integration_instance_revision AS r
                    ON r.org_id=p.org_id AND r.project_id=p.project_id
                   AND r.instance_pk=p.instance_pk
                   AND r.revision=p.instance_revision
                 WHERE p.org_id=%s AND p.project_id=%s AND p.case_pk=%s
                """,
                (ORG, PROJECT, created.case_pk, ORG, PROJECT, created.case_pk),
            ).fetchone()
        assert {
            mirrors["cutoff_at"],
            mirrors["updated_at"],
            mirrors["snapshot_cutoff"],
            mirrors["revision_created"],
        } == {refreshed.cutoff_at}
        assert mirrors["next_projection_at"] is None
        assert (mirrors["snapshot_revision"], mirrors["etag_version"]) == (3, 3)
        assert mirrors["events"] == 3

        repeated = projector.refresh_case_if_due(
            org_id=ORG, project_id=PROJECT, case_id=created.case_id
        )
        assert not repeated.projected and not repeated.stage_changed
        assert (repeated.snapshot_revision, repeated.etag_version) == (3, 3)
        with connect_factory() as conn:
            assert (
                conn.execute(
                    "SELECT COUNT(*) AS count FROM integration_stage_event"
                ).fetchone()["count"]
                == 3
            )
        _assert_python_pg_stage_match(connect_factory, created.case_pk)


@pytest.mark.parametrize("outcome", ["invalid", "revoked"])
def test_latest_negative_or_revoke_reprojects_and_unchanged_stage_adds_no_event(
    outcome: str,
) -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store, clock, created, source, now = _seed_connection_verified_case(
            connect_factory
        )
        clock.value = now + timedelta(seconds=1)
        latest = _evidence(
            evidence_type="source_connection",
            evidence_id=source.evidence_id,
            revision=2,
            outcome=outcome,
            observed_at=source.observed_at,
            recorded_at=clock.value,
            revoked_at=clock.value if outcome == "revoked" else None,
        )
        store.append_evidence(
            org_id=ORG,
            project_id=PROJECT,
            case_id=created.case_id,
            evidence=latest,
        )
        clock.value = now + timedelta(seconds=2)
        negative = store.project_case(
            org_id=ORG,
            project_id=PROJECT,
            case_id=created.case_id,
            if_match_etag=2,
            cause=("negative_observed" if outcome == "invalid" else "evidence_revoked"),
        )
        assert negative.response.computed_stage.value == "planned"
        assert negative.stage_event is not None

        clock.value = now + timedelta(seconds=3)
        unchanged = store.project_case(
            org_id=ORG,
            project_id=PROJECT,
            case_id=created.case_id,
            if_match_etag=3,
            cause="projection_rebuilt",
        )
        assert unchanged.response.computed_stage.value == "planned"
        assert unchanged.stage_event is None
        with connect_factory() as conn:
            row = conn.execute(
                """
                SELECT snapshot_json,
                       (SELECT COUNT(*) FROM integration_stage_event
                         WHERE org_id=%s AND project_id=%s AND case_pk=%s) AS events
                  FROM integration_evidence_snapshot
                 WHERE org_id=%s AND project_id=%s AND case_pk=%s
                 ORDER BY snapshot_revision DESC LIMIT 1
                """,
                (ORG, PROJECT, created.case_pk, ORG, PROJECT, created.case_pk),
            ).fetchone()
        source_heads = [
            item
            for item in row["snapshot_json"]["evidence"]
            if item["evidenceType"] == "source_connection"
        ]
        assert [(item["revision"], item["outcome"]) for item in source_heads] == [
            (2, outcome)
        ]
        assert row["events"] == 3
        _assert_python_pg_stage_match(connect_factory, created.case_pk)


def test_expiry_batch_is_bounded_repeatable_and_skips_locked_cases() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        expiry = _db_now(connect_factory) - timedelta(seconds=1)
        cases = [
            _seed_connection_verified_case(connect_factory, source_expiry=expiry)[2]
            for _ in range(2)
        ]
        projector = IntegrationExpiryProjector(connect_factory)
        first = projector.project_expired_batch(batch_size=1)
        second = projector.project_expired_batch(batch_size=1)
        repeated = projector.project_expired_batch(batch_size=1)
        assert first.selected_count == first.projected_count == 1
        assert second.selected_count == second.projected_count == 1
        assert set(first.selected_case_ids + second.selected_case_ids) == {
            item.case_id for item in cases
        }
        assert repeated.selected_count == repeated.projected_count == 0

        third = _seed_connection_verified_case(connect_factory, source_expiry=expiry)[2]
        with connect_factory() as locker:
            locker.execute(
                """
                SELECT 1 FROM integration_case AS c
                JOIN integration_instance AS i
                  ON i.org_id=c.org_id AND i.project_id=c.project_id
                 AND i.case_pk=c.case_pk
                JOIN integration_case_projection AS p
                  ON p.org_id=c.org_id AND p.project_id=c.project_id
                 AND p.case_pk=c.case_pk
                WHERE c.org_id=%s AND c.project_id=%s AND c.case_pk=%s
                FOR UPDATE OF c,i,p
                """,
                (ORG, PROJECT, third.case_pk),
            )
            skipped = projector.project_expired_batch(batch_size=10)
            assert skipped.selected_count == 0
            locker.rollback()
        assert projector.project_expired_batch(batch_size=10).selected_count == 1


def test_expiry_batch_isolates_poison_case_and_projects_later_healthy_case() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        poisoned = _seed_connection_verified_case(
            connect_factory, source_expiry_offset=timedelta(seconds=-1.5)
        )[2]
        healthy = _seed_connection_verified_case(
            connect_factory, source_expiry_offset=timedelta(seconds=-1)
        )[2]
        with connect_factory() as conn:
            conn.execute("ALTER TABLE integration_evidence DISABLE TRIGGER USER")
            conn.execute(
                """UPDATE integration_evidence SET evidence_hash=%s
                     WHERE org_id=%s AND project_id=%s AND case_pk=%s
                       AND evidence_type='source_connection'""",
                (ZERO_HASH, ORG, PROJECT, poisoned.case_pk),
            )
            conn.execute("ALTER TABLE integration_evidence ENABLE TRIGGER USER")
            conn.commit()

        result = IntegrationExpiryProjector(connect_factory).project_expired_batch()
        assert result.selected_count == 2
        assert result.projected_count == 1
        assert result.processed_case_refs == result.selected_case_refs
        assert result.failed_case_refs == (f"{ORG}/{PROJECT}/{poisoned.case_id}",)
        assert result.failures[0].code == "evidence_integrity_corrupt"
        assert result.results[0].case_id == healthy.case_id
        assert result.results[0].computed_stage.value == "planned"

        def _state(case_pk: uuid.UUID) -> tuple[int, int, int, int]:
            with connect_factory() as conn:
                row = conn.execute(
                    """SELECT i.current_revision,i.etag_version,p.snapshot_revision,
                              (SELECT COUNT(*) FROM integration_stage_event
                                WHERE org_id=%s AND project_id=%s
                                  AND case_pk=%s) AS events
                         FROM integration_instance AS i
                         JOIN integration_case_projection AS p
                           ON p.org_id=i.org_id AND p.project_id=i.project_id
                          AND p.instance_pk=i.instance_pk
                        WHERE i.org_id=%s AND i.project_id=%s AND i.case_pk=%s""",
                    (ORG, PROJECT, case_pk, ORG, PROJECT, case_pk),
                ).fetchone()
            return (
                row["current_revision"],
                row["etag_version"],
                row["snapshot_revision"],
                row["events"],
            )

        assert _state(poisoned.case_pk) == (2, 2, 2, 2)
        assert _state(healthy.case_pk) == (3, 3, 3, 3)


@pytest.mark.parametrize("batch_size", [True, 0, 1001, 1.5])
def test_expiry_batch_rejects_unsafe_size(batch_size: object) -> None:
    with pytest.raises(ValueError):
        IntegrationExpiryProjector().project_expired_batch(batch_size=batch_size)  # type: ignore[arg-type]
