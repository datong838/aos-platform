"""Real PostgreSQL tests for the M4 Integration Case migration."""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from aos_api.db import connect
from psycopg import IntegrityError, errors, sql
from psycopg.types.json import Jsonb

API_ROOT = Path(__file__).resolve().parents[2]
BASE_MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
    API_ROOT / "alembic/versions/228asset1_composition_installation.py",
)
MIGRATION_PATH = API_ROOT / "alembic/versions/228asset2_integration_cases.py"
M4_TABLES = (
    "integration_case",
    "integration_instance",
    "integration_instance_revision",
    "integration_evidence",
    "integration_evidence_snapshot",
    "integration_stage_event",
    "integration_case_projection",
    "integration_case_command",
)
STAGES = (
    "planned",
    "connection_verified",
    "data_verified",
    "ontology_verified",
    "logic_verified",
    "workshop_verified",
    "production_ready",
    "production_active",
)
ORG = "org-m4"
PROJECT = "project-m4"
CASE_PK = uuid.UUID("40000000-0000-4000-8000-000000000001")
CASE_ID = uuid.UUID("40000000-0000-4000-8000-000000000002")
INSTANCE_PK = uuid.UUID("41000000-0000-4000-8000-000000000001")
COMPOSITION_PK = uuid.UUID("42000000-0000-4000-8000-000000000001")
COMPOSITION_ID = uuid.UUID("42000000-0000-4000-8000-000000000002")
INSTALLATION_PK = uuid.UUID("43000000-0000-4000-8000-000000000001")
INSTALLATION_ID = uuid.UUID("43000000-0000-4000-8000-000000000002")
ZERO_HASH = "sha256:" + "0" * 64
CUTOFF = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


def _load_migration(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_statements(path: Path, name: str, operation: str) -> list[str]:
    statements: list[str] = []
    module = _load_migration(path, name)
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value = []
    with (
        patch.object(module.op, "execute", statements.append),
        patch.object(module.op, "get_bind", return_value=connection),
    ):
        getattr(module, operation)()
    return statements


def _all_upgrade_statements() -> list[str]:
    statements: list[str] = []
    for index, path in enumerate((*BASE_MIGRATIONS, MIGRATION_PATH)):
        statements.extend(
            _migration_statements(path, f"m4_upgrade_{index}", "upgrade")
        )
    return statements


@contextmanager
def _isolated_m4_schema() -> Iterator[Callable[[], object]]:
    schema = f"integration_case_migration_{uuid.uuid4().hex}"
    created = False
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            created = True
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            for statement in _all_upgrade_statements():
                conn.execute(statement)
            conn.commit()
    except Exception as exc:
        if not created:
            pytest.skip(f"PG unavailable: {exc}")
        raise

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield conn

    try:
        yield scoped_connect
    finally:
        if created:
            with connect() as conn:
                conn.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
                conn.commit()


def _assert_integrity_violation(
    conn: object,
    statements: str | Sequence[str],
    expected: type[IntegrityError] = IntegrityError,
    *,
    defer_check: bool = False,
) -> None:
    savepoint = sql.Identifier(f"expected_failure_{uuid.uuid4().hex}")
    conn.execute(sql.SQL("SAVEPOINT {}").format(savepoint))
    with pytest.raises(expected):
        for statement in (statements,) if isinstance(statements, str) else statements:
            conn.execute(statement)
        if defer_check:
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(savepoint))
    conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(savepoint))
    conn.execute("SET CONSTRAINTS ALL DEFERRED")


def _canonical_hash(conn: object, value: dict) -> str:
    return conn.execute(
        "SELECT canonical_integration_case_sha256(%s::JSONB) AS hash",
        (Jsonb(value),),
    ).fetchone()["hash"]


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _stage_gates(stage: str) -> list[dict[str, object]]:
    rank = STAGES.index(stage)
    result: list[dict[str, object]] = []
    for index, item in enumerate(STAGES):
        if index <= rank:
            status = "satisfied"
        elif index == rank + 1:
            status = "blocked"
        else:
            status = "not_evaluated"
        result.append(
            {
                "stage": item,
                "status": status,
                "evidenceRefs": [],
                "reasonRefs": [] if status != "blocked" else ["missing:evidence"],
            }
        )
    return result


def _blockers(stage: str, when: datetime) -> list[dict[str, object]]:
    return [
        {
            "blockerId": "44000000-0000-4000-8000-000000000001",
            "code": "missing_evidence",
            "severity": "high",
            "status": "open",
            "gate": STAGES[min(STAGES.index(stage) + 1, len(STAGES) - 1)],
            "reasonRefs": ["missing:evidence"],
            "evidenceRefs": [],
            "owner": None,
            "firstObservedAt": _iso(when),
            "updatedAt": _iso(when),
        }
    ]


def _seed_active_installation(conn: object) -> str:
    request = {"requested": []}
    registry = {"schemaVersion": "aos.dev/registry-snapshot/v1alpha1", "candidates": []}
    conn.execute(
        """
        INSERT INTO bundle_composition (
          org_id, project_id, composition_pk, composition_id,
          request_json, request_hash, registry_snapshot_json,
          registry_snapshot_hash, resolver_version, created_by
        ) VALUES (%s,%s,%s,%s,%s,
          canonical_bundle_control_sha256(%s::JSONB),%s,
          canonical_bundle_control_sha256(%s::JSONB),
          'aos-resolver/1.0.0','resolver:test')
        """,
        (
            ORG,
            PROJECT,
            COMPOSITION_PK,
            COMPOSITION_ID,
            Jsonb(request),
            Jsonb(request),
            Jsonb(registry),
            Jsonb(registry),
        ),
    )
    diff = {"baseline": {}, "target": {}, "added": {}, "removed": {}, "unchanged": {}}
    lock = {
        "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
        "resolverVersion": "aos-resolver/1.0.0",
        "request": {},
        "registrySnapshotHash": ZERO_HASH,
        "resolved": [],
        "edges": [],
        "capabilityProviders": [],
        "permissionDiff": diff,
        "migrationPlan": diff,
        "contributionDiff": diff,
        "currentInstallationRef": None,
    }
    lock_hash = conn.execute(
        "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
        (Jsonb(lock),),
    ).fetchone()["hash"]
    diff_hash = conn.execute(
        "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
        (Jsonb(diff),),
    ).fetchone()["hash"]
    conn.execute(
        """
        INSERT INTO bundle_composition_lock (
          org_id,project_id,composition_pk,revision,lock_payload,lock_hash,
          permission_diff_json,permission_diff_hash,
          migration_plan_json,migration_plan_hash,
          contribution_diff_json,contribution_diff_hash,created_by
        ) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,'resolver:test')
        """,
        (
            ORG,
            PROJECT,
            COMPOSITION_PK,
            Jsonb(lock),
            lock_hash,
            Jsonb(diff),
            diff_hash,
            Jsonb(diff),
            diff_hash,
            Jsonb(diff),
            diff_hash,
        ),
    )
    for table in (
        "bundle_installation",
        "bundle_installation_revision",
        "bundle_installation_event",
    ):
        conn.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(sql.Identifier(table)))
    try:
        conn.execute(
            """
            INSERT INTO bundle_installation (
              org_id,project_id,installation_pk,installation_id,display_name,
              current_revision,active_revision,previous_active_revision,
              etag_version,created_by
            ) VALUES (%s,%s,%s,%s,'M4 installation',1,1,NULL,1,'test:seed')
            """,
            (ORG, PROJECT, INSTALLATION_PK, INSTALLATION_ID),
        )
        conn.execute(
            """
            INSERT INTO bundle_installation_revision (
              org_id,project_id,installation_pk,revision,parent_revision,state,
              composition_pk,lock_revision,lock_hash,permission_diff_hash,
              migration_plan_hash,contribution_diff_hash,overlay_revision,
              requested_by
            ) VALUES (%s,%s,%s,1,NULL,'active',%s,1,%s,%s,%s,%s,
                      'overlay-v1','test:seed')
            """,
            (
                ORG,
                PROJECT,
                INSTALLATION_PK,
                COMPOSITION_PK,
                lock_hash,
                diff_hash,
                diff_hash,
                diff_hash,
            ),
        )
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    finally:
        for table in (
            "bundle_installation_event",
            "bundle_installation_revision",
            "bundle_installation",
        ):
            conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(sql.Identifier(table)))
        conn.execute("SET CONSTRAINTS ALL DEFERRED")
    return lock_hash


def _insert_current_case_basis(conn: object) -> str:
    lock_hash = _seed_active_installation(conn)
    conn.execute(
        """
        INSERT INTO integration_case (
          org_id,project_id,case_pk,case_id,scope,display_name,owner,
          required_markings
        ) VALUES (%s,%s,%s,%s,'current','M4 current case','owner:test','[]')
        """,
        (ORG, PROJECT, CASE_PK, CASE_ID),
    )
    conn.execute(
        """
        INSERT INTO integration_instance (
          org_id,project_id,instance_pk,case_pk,current_revision,etag_version
        ) VALUES (%s,%s,%s,%s,1,1)
        """,
        (ORG, PROJECT, INSTANCE_PK, CASE_PK),
    )
    _insert_instance_revision(conn, 1, lock_hash)
    return lock_hash


def _insert_instance_revision(conn: object, revision: int, lock_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO integration_instance_revision (
          org_id,project_id,instance_pk,revision,parent_revision,
          installation_pk,installation_revision,composition_pk,lock_revision,
          lock_hash,overlay_revision,required_markings
        ) VALUES (%s,%s,%s,%s,%s,%s,1,%s,1,%s,'overlay-v1','[]')
        """,
        (
            ORG,
            PROJECT,
            INSTANCE_PK,
            revision,
            revision - 1 if revision > 1 else None,
            INSTALLATION_PK,
            COMPOSITION_PK,
            lock_hash,
        ),
    )


def _advance_instance(conn: object, revision: int, lock_hash: str) -> None:
    _insert_instance_revision(conn, revision, lock_hash)
    conn.execute(
        """
        UPDATE integration_instance
           SET current_revision=%s, etag_version=%s,
               updated_at=updated_at + INTERVAL '1 second'
         WHERE org_id=%s AND project_id=%s AND instance_pk=%s
        """,
        (revision, revision, ORG, PROJECT, INSTANCE_PK),
    )


def _insert_evidence(
    conn: object,
    *,
    evidence_pk: uuid.UUID,
    evidence_id: uuid.UUID,
    evidence_type: str,
    series_key: str,
    claims: dict[str, object],
    observed_at: datetime,
    recorded_at: datetime,
    evidence_hash_override: str | None = None,
    revision: int = 1,
    outcome: str = "valid",
) -> dict[str, object]:
    envelope: dict[str, object] = {
        "evidenceId": str(evidence_id),
        "revision": revision,
        "evidenceType": evidence_type,
        "seriesKey": series_key,
        "subjectRef": "case:subject",
        "artifactRef": f"artifact:{series_key}",
        "artifactHash": ZERO_HASH,
        "outcome": outcome,
        "observedAt": _iso(observed_at),
        "expiresAt": None,
        "revokedAt": None,
        "requiredMarkings": [],
        "producer": "producer:test",
        "claims": claims,
        "recordedAt": _iso(recorded_at),
    }
    envelope["evidenceHash"] = evidence_hash_override or _canonical_hash(conn, envelope)
    conn.execute(
        """
        INSERT INTO integration_evidence (
          org_id,project_id,evidence_pk,evidence_id,case_pk,revision,
          evidence_type,series_key,subject_ref,artifact_ref,artifact_hash,
          outcome,observed_at,expires_at,revoked_at,required_markings,
          producer,claims_json,envelope_json,evidence_hash,recorded_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'case:subject',%s,%s,%s,
                  %s,NULL,NULL,'[]','producer:test',%s,%s,%s,%s)
        """,
        (
            ORG,
            PROJECT,
            evidence_pk,
            evidence_id,
            CASE_PK,
            revision,
            evidence_type,
            series_key,
            f"artifact:{series_key}",
            ZERO_HASH,
            outcome,
            observed_at,
            Jsonb(claims),
            Jsonb(envelope),
            envelope["evidenceHash"],
            recorded_at,
        ),
    )
    return envelope


def _insert_snapshot_projection(
    conn: object,
    *,
    revision: int,
    stage: str,
    cutoff: datetime,
    evidence: list[dict[str, object]],
    old_stage: str | None,
    gates_override: list[dict[str, object]] | None = None,
) -> str:
    gates = gates_override or _stage_gates(stage)
    blocker_refs = [] if stage == "production_active" else ["missing:evidence"]
    snapshot: dict[str, object] = {
        "caseId": str(CASE_ID),
        "snapshotRevision": revision,
        "instanceRevision": revision,
        "cutoffAt": _iso(cutoff),
        "nextProjectionAt": None,
        "evidence": evidence,
        "computedStage": stage,
        "stagePolicyVersion": "aos.integration-stage/v1",
        "stageGates": gates,
        "blockerRefs": blocker_refs,
    }
    snapshot_hash = _canonical_hash(conn, snapshot)
    snapshot["snapshotHash"] = snapshot_hash
    conn.execute(
        """
        INSERT INTO integration_evidence_snapshot (
          org_id,project_id,case_pk,snapshot_revision,instance_pk,
          instance_revision,snapshot_json,snapshot_hash,cutoff_at,
          next_projection_at,computed_stage,stage_policy_version,
          evidence_count,stage_gates_json,blocker_refs_json,etag_version
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,
                  'aos.integration-stage/v1',%s,%s,%s,%s)
        """,
        (
            ORG,
            PROJECT,
            CASE_PK,
            revision,
            INSTANCE_PK,
            revision,
            Jsonb(snapshot),
            snapshot_hash,
            cutoff,
            stage,
            len(evidence),
            Jsonb(gates),
            Jsonb(blocker_refs),
            revision,
        ),
    )
    if old_stage != stage:
        conn.execute(
            """
            INSERT INTO integration_stage_event (
              org_id,project_id,case_pk,sequence,snapshot_revision,
              old_stage,new_stage,cause,reason_refs
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]')
            """,
            (
                ORG,
                PROJECT,
                CASE_PK,
                1 if old_stage is None else 2,
                revision,
                old_stage,
                stage,
                "created" if old_stage is None else "evidence_added",
            ),
        )
    blockers = _blockers(stage, cutoff)
    if revision == 1:
        conn.execute(
            """
            INSERT INTO integration_case_projection (
              org_id,project_id,case_pk,instance_pk,instance_revision,
              snapshot_revision,computed_stage,stage_policy_version,
              cutoff_at,next_projection_at,stage_gates_json,blockers_json,
              connector_count,pipeline_count,dataset_row_count,latency_ms,
              blocker_count,etag_version
            ) VALUES (%s,%s,%s,%s,1,1,%s,'aos.integration-stage/v1',
                      %s,NULL,%s,%s,NULL,NULL,NULL,NULL,1,1)
            """,
            (
                ORG,
                PROJECT,
                CASE_PK,
                INSTANCE_PK,
                stage,
                cutoff,
                Jsonb(gates),
                Jsonb(blockers),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE integration_case_projection
               SET instance_revision=%s,snapshot_revision=%s,computed_stage=%s,
                   cutoff_at=%s,stage_gates_json=%s,blockers_json=%s,
                   blocker_count=1,etag_version=%s,
                   updated_at=updated_at + INTERVAL '1 second'
             WHERE org_id=%s AND project_id=%s AND case_pk=%s
            """,
            (
                revision,
                revision,
                stage,
                cutoff,
                Jsonb(gates),
                Jsonb(blockers),
                revision,
                ORG,
                PROJECT,
                CASE_PK,
            ),
        )
    return snapshot_hash


def _insert_create_receipt(conn: object) -> None:
    conn.execute(
        """
        INSERT INTO integration_case_command (
          org_id,project_id,operation,idempotency_key,case_pk,subject,
          request_hash,if_match_etag,status_code,response_json,response_etag
        ) VALUES (%s,%s,'integration_cases.create','create-1',%s,'subject:test',
                  %s,NULL,201,%s,'"1"')
        """,
        (
            ORG,
            PROJECT,
            CASE_PK,
            ZERO_HASH,
            Jsonb({"caseId": str(CASE_ID)}),
        ),
    )


def test_migration_shape_single_head_and_empty_upgrade() -> None:
    module = _load_migration(MIGRATION_PATH, "m4_migration_shape")
    upgrade_sql = "\n".join(
        _migration_statements(MIGRATION_PATH, "m4_shape_upgrade", "upgrade")
    )
    downgrade_sql = "\n".join(
        _migration_statements(MIGRATION_PATH, "m4_shape_downgrade", "downgrade")
    )
    script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))

    assert module.revision == "228assetintegration"
    assert module.down_revision == "228assetinstall"
    assert script.get_heads() == ["228assetintegration"]
    for table in M4_TABLES:
        assert f"CREATE TABLE {table}" in upgrade_sql
    assert "canonical_integration_case_sha256" in upgrade_sql
    assert "integration_snapshot_computed_stage" in upgrade_sql
    assert "canonical data exists" in downgrade_sql
    assert "DROP TABLE IF EXISTS" not in downgrade_sql

    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        assert all(
            conn.execute("SELECT to_regclass(%s) AS name", (table,)).fetchone()["name"]
            == table
            for table in M4_TABLES
        )


def test_valid_current_case_evidence_snapshot_stage_and_projection_tail() -> None:
    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash = _insert_current_case_basis(conn)
        _insert_snapshot_projection(
            conn,
            revision=1,
            stage="planned",
            cutoff=CUTOFF,
            evidence=[],
            old_stage=None,
        )
        _insert_create_receipt(conn)
        conn.commit()

        _advance_instance(conn, 2, lock_hash)
        source = _insert_evidence(
            conn,
            evidence_pk=uuid.UUID("45000000-0000-4000-8000-000000000001"),
            evidence_id=uuid.UUID("45000000-0000-4000-8000-000000000002"),
            evidence_type="source_connection",
            series_key="a-source",
            claims={
                "connectionRef": "connection:primary",
                "authMode": "oauth",
                "readProbe": True,
                "tenantBinding": True,
            },
            observed_at=CUTOFF + timedelta(seconds=1),
            recorded_at=CUTOFF + timedelta(seconds=2),
        )
        tenant = _insert_evidence(
            conn,
            evidence_pk=uuid.UUID("46000000-0000-4000-8000-000000000001"),
            evidence_id=uuid.UUID("46000000-0000-4000-8000-000000000002"),
            evidence_type="tenant_isolation",
            series_key="b-tenant",
            claims={
                "positiveTenant": "tenant:positive",
                "negativeTenant": "tenant:negative",
                "crossTenantDenied": True,
            },
            observed_at=CUTOFF + timedelta(seconds=1),
            recorded_at=CUTOFF + timedelta(seconds=2),
        )
        snapshot_hash = _insert_snapshot_projection(
            conn,
            revision=2,
            stage="connection_verified",
            cutoff=CUTOFF + timedelta(seconds=3),
            evidence=[source, tenant],
            old_stage="planned",
        )
        conn.execute(
            """
            INSERT INTO integration_case_command (
              org_id,project_id,operation,idempotency_key,case_pk,subject,
              request_hash,if_match_etag,status_code,response_json,response_etag
            ) VALUES (%s,%s,'integration_cases.project','project-1',%s,
                      'subject:test',%s,1,201,%s,'"2"')
            """,
            (
                ORG,
                PROJECT,
                CASE_PK,
                ZERO_HASH,
                Jsonb({"snapshotHash": snapshot_hash}),
            ),
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT i.current_revision,i.etag_version,p.snapshot_revision,
                   p.computed_stage,e.snapshot_hash
              FROM integration_instance AS i
              JOIN integration_case_projection AS p
                ON p.org_id=i.org_id AND p.project_id=i.project_id
               AND p.case_pk=i.case_pk
              JOIN integration_evidence_snapshot AS e
                ON e.org_id=p.org_id AND e.project_id=p.project_id
               AND e.case_pk=p.case_pk
               AND e.snapshot_revision=p.snapshot_revision
            """
        ).fetchone()
        assert row == {
            "current_revision": 2,
            "etag_version": 2,
            "snapshot_revision": 2,
            "computed_stage": "connection_verified",
            "snapshot_hash": snapshot_hash,
        }
        events = conn.execute(
            """
            SELECT sequence,old_stage,new_stage,snapshot_revision
              FROM integration_stage_event ORDER BY sequence
            """
        ).fetchall()
        assert events == [
            {
                "sequence": 1,
                "old_stage": None,
                "new_stage": "planned",
                "snapshot_revision": 1,
            },
            {
                "sequence": 2,
                "old_stage": "planned",
                "new_stage": "connection_verified",
                "snapshot_revision": 2,
            },
        ]


def test_direct_sql_hash_stage_tenant_and_immutability_attacks_fail_closed() -> None:
    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        _insert_current_case_basis(conn)
        _insert_snapshot_projection(
            conn,
            revision=1,
            stage="planned",
            cutoff=CUTOFF,
            evidence=[],
            old_stage=None,
        )
        _insert_create_receipt(conn)
        conn.commit()

        _assert_integrity_violation(
            conn,
            "UPDATE integration_evidence_snapshot SET computed_stage='production_active'",
            errors.CheckViolation,
        )


def test_snapshot_rejects_forged_stage_bad_hash_claims_and_missing_latest_head() -> None:
    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash = _insert_current_case_basis(conn)
        savepoint = sql.Identifier(f"forged_stage_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(savepoint))
        with pytest.raises(errors.CheckViolation):
            _insert_snapshot_projection(
                conn,
                revision=1,
                stage="production_active",
                cutoff=CUTOFF,
                evidence=[],
                old_stage=None,
            )
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(savepoint))
        forged_gates = _stage_gates("planned")
        forged_gates[1]["status"] = "satisfied"
        forged_gates_savepoint = sql.Identifier(
            f"forged_gates_{uuid.uuid4().hex}"
        )
        conn.execute(sql.SQL("SAVEPOINT {}").format(forged_gates_savepoint))
        with pytest.raises(errors.CheckViolation):
            _insert_snapshot_projection(
                conn,
                revision=1,
                stage="planned",
                cutoff=CUTOFF,
                evidence=[],
                old_stage=None,
                gates_override=forged_gates,
            )
        conn.execute(
            sql.SQL("ROLLBACK TO SAVEPOINT {}").format(forged_gates_savepoint)
        )
        conn.execute(
            sql.SQL("RELEASE SAVEPOINT {}").format(forged_gates_savepoint)
        )
        _insert_snapshot_projection(
            conn,
            revision=1,
            stage="planned",
            cutoff=CUTOFF,
            evidence=[],
            old_stage=None,
        )
        _insert_create_receipt(conn)
        conn.commit()

        _advance_instance(conn, 2, lock_hash)
        bad_hash_savepoint = sql.Identifier(f"bad_hash_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(bad_hash_savepoint))
        with pytest.raises(errors.CheckViolation):
            _insert_evidence(
                conn,
                evidence_pk=uuid.UUID("47000000-0000-4000-8000-000000000001"),
                evidence_id=uuid.UUID("47000000-0000-4000-8000-000000000002"),
                evidence_type="source_connection",
                series_key="a-bad-hash",
                claims={
                    "connectionRef": "connection:primary",
                    "authMode": "oauth",
                    "readProbe": True,
                    "tenantBinding": True,
                },
                observed_at=CUTOFF + timedelta(seconds=1),
                recorded_at=CUTOFF + timedelta(seconds=2),
                evidence_hash_override=ZERO_HASH,
            )
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(bad_hash_savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(bad_hash_savepoint))

        bad_claims_savepoint = sql.Identifier(f"bad_claims_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(bad_claims_savepoint))
        with pytest.raises(errors.CheckViolation):
            _insert_evidence(
                conn,
                evidence_pk=uuid.UUID("48000000-0000-4000-8000-000000000001"),
                evidence_id=uuid.UUID("48000000-0000-4000-8000-000000000002"),
                evidence_type="source_connection",
                series_key="a-bad-claims",
                claims={
                    "connectionRef": "connection:primary",
                    "authMode": "oauth",
                    "readProbe": True,
                    "tenantBinding": True,
                    "metadata": {"stage": "production_active"},
                },
                observed_at=CUTOFF + timedelta(seconds=1),
                recorded_at=CUTOFF + timedelta(seconds=2),
            )
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(bad_claims_savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(bad_claims_savepoint))

        source = _insert_evidence(
            conn,
            evidence_pk=uuid.UUID("49000000-0000-4000-8000-000000000001"),
            evidence_id=uuid.UUID("49000000-0000-4000-8000-000000000002"),
            evidence_type="source_connection",
            series_key="a-source",
            claims={
                "connectionRef": "connection:primary",
                "authMode": "oauth",
                "readProbe": True,
                "tenantBinding": True,
            },
            observed_at=CUTOFF + timedelta(seconds=1),
            recorded_at=CUTOFF + timedelta(seconds=2),
        )
        latest_negative = _insert_evidence(
            conn,
            evidence_pk=uuid.UUID("49000000-0000-4000-8000-000000000001"),
            evidence_id=uuid.UUID("49000000-0000-4000-8000-000000000002"),
            evidence_type="source_connection",
            series_key="a-source",
            claims={
                "connectionRef": "connection:primary",
                "authMode": "oauth",
                "readProbe": True,
                "tenantBinding": True,
            },
            observed_at=CUTOFF + timedelta(seconds=2),
            recorded_at=CUTOFF + timedelta(seconds=3),
            revision=2,
            outcome="invalid",
        )
        omission_savepoint = sql.Identifier(f"omission_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(omission_savepoint))
        with pytest.raises(errors.CheckViolation):
            _insert_snapshot_projection(
                conn,
                revision=2,
                stage="planned",
                cutoff=CUTOFF + timedelta(seconds=4),
                evidence=[source],
                old_stage="planned",
            )
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(omission_savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(omission_savepoint))
        _insert_snapshot_projection(
            conn,
            revision=2,
            stage="planned",
            cutoff=CUTOFF + timedelta(seconds=4),
            evidence=[latest_negative],
            old_stage="planned",
        )
        conn.execute(
            """
            INSERT INTO integration_case_command (
              org_id,project_id,operation,idempotency_key,case_pk,subject,
              request_hash,if_match_etag,status_code,response_json,response_etag
            ) VALUES (%s,%s,'integration_cases.project','project-no-stage',%s,
                      'subject:test',%s,1,201,'{}','"2"')
            """,
            (ORG, PROJECT, CASE_PK, ZERO_HASH),
        )
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) AS count FROM integration_stage_event"
        ).fetchone()["count"] == 1
        assert conn.execute(
            """
            SELECT integration_claims_pass(
              'mapping_validation',
              '{"mappingRef":"mapping:x","coverage":0.99,
                "linkValidationPassed":true}'::JSONB
            ) AS passed
            """
        ).fetchone()["passed"] is False


def test_reference_binding_metrics_evidence_and_commands_are_isolated() -> None:
    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        conn.execute(
            """
            INSERT INTO integration_case (
              org_id,project_id,case_pk,case_id,scope,display_name,owner,
              required_markings
            ) VALUES (%s,%s,%s,%s,'reference','Reference case',NULL,'[]')
            """,
            (ORG, PROJECT, CASE_PK, CASE_ID),
        )
        conn.execute(
            """
            INSERT INTO integration_instance (
              org_id,project_id,instance_pk,case_pk,current_revision,etag_version
            ) VALUES (%s,%s,%s,%s,1,1)
            """,
            (ORG, PROJECT, INSTANCE_PK, CASE_PK),
        )
        conn.execute(
            """
            INSERT INTO integration_instance_revision (
              org_id,project_id,instance_pk,revision,parent_revision,
              installation_pk,installation_revision,composition_pk,
              lock_revision,lock_hash,overlay_revision,required_markings
            ) VALUES (%s,%s,%s,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'[]')
            """,
            (ORG, PROJECT, INSTANCE_PK),
        )
        _insert_snapshot_projection(
            conn,
            revision=1,
            stage="planned",
            cutoff=CUTOFF,
            evidence=[],
            old_stage=None,
        )
        conn.commit()

        _assert_integrity_violation(
            conn,
            """
            UPDATE integration_instance
               SET current_revision=2,etag_version=2,
                   updated_at=updated_at + INTERVAL '1 second'
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "UPDATE integration_case_projection SET connector_count=1",
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO integration_case_command (
              org_id,project_id,operation,idempotency_key,case_pk,subject,
              request_hash,if_match_etag,status_code,response_json,response_etag
            ) VALUES (
              'org-m4','project-m4','integration_cases.create','reference',
              '40000000-0000-4000-8000-000000000001','subject:test',
              'sha256:0000000000000000000000000000000000000000000000000000000000000000',
              NULL,201,'{}','"1"'
            )
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO integration_evidence (
              org_id,project_id,evidence_pk,evidence_id,case_pk,revision,
              evidence_type,series_key,subject_ref,artifact_ref,artifact_hash,
              outcome,observed_at,required_markings,producer,claims_json,
              envelope_json,evidence_hash,recorded_at
            ) VALUES (
              'org-m4','project-m4',
              '50000000-0000-4000-8000-000000000001',
              '50000000-0000-4000-8000-000000000002',
              '40000000-0000-4000-8000-000000000001',1,
              'source_connection','late','case:subject','artifact:late',
              'sha256:0000000000000000000000000000000000000000000000000000000000000000',
              'valid','2026-08-03T12:00:00Z','[]','producer:test',
              '{}','{}',
              'sha256:0000000000000000000000000000000000000000000000000000000000000000',
              '2026-08-03T12:00:00Z'
            )
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "TRUNCATE integration_case CASCADE",
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO integration_instance_revision (
              org_id,project_id,instance_pk,revision,parent_revision,
              installation_pk,installation_revision,composition_pk,
              lock_revision,lock_hash,overlay_revision,required_markings
            ) VALUES (
              'org-other','project-m4',
              '41000000-0000-4000-8000-000000000001',2,1,
              '43000000-0000-4000-8000-000000000001',1,
              '42000000-0000-4000-8000-000000000001',1,
              'sha256:0000000000000000000000000000000000000000000000000000000000000000',
              'overlay-v1','[]'
            )
            """,
            IntegrityError,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO integration_case_command (
              org_id,project_id,operation,idempotency_key,case_pk,subject,
              request_hash,if_match_etag,status_code,response_json,response_etag
            ) VALUES (
              'org-m4','project-m4','integration_cases.project','bad-etag',
              '40000000-0000-4000-8000-000000000001','subject:test',
              'sha256:0000000000000000000000000000000000000000000000000000000000000000',
              99,201,'{}','"1"'
            )
            """,
            errors.CheckViolation,
        )


def test_nonempty_downgrade_blocks_and_empty_down_up_round_trip() -> None:
    downgrade = _migration_statements(
        MIGRATION_PATH, "m4_downgrade_round_trip", "downgrade"
    )
    upgrade = _migration_statements(
        MIGRATION_PATH, "m4_reupgrade_round_trip", "upgrade"
    )
    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        _insert_current_case_basis(conn)
        _insert_snapshot_projection(
            conn,
            revision=1,
            stage="planned",
            cutoff=CUTOFF,
            evidence=[],
            old_stage=None,
        )
        _insert_create_receipt(conn)
        conn.commit()
        _assert_integrity_violation(conn, downgrade[0], errors.CheckViolation)
        assert conn.execute(
            "SELECT to_regclass('integration_case') AS name"
        ).fetchone()["name"] == "integration_case"

    with _isolated_m4_schema() as scoped_connect, scoped_connect() as conn:
        for statement in downgrade:
            conn.execute(statement)
        assert all(
            conn.execute("SELECT to_regclass(%s) AS name", (table,)).fetchone()["name"]
            is None
            for table in M4_TABLES
        )
        assert conn.execute(
            "SELECT to_regprocedure('canonical_asset_registry_jsonb(jsonb)') AS fn"
        ).fetchone()["fn"] == "canonical_asset_registry_jsonb(jsonb)"
        assert conn.execute(
            "SELECT to_regprocedure('canonical_bundle_control_sha256(jsonb)') AS fn"
        ).fetchone()["fn"] == "canonical_bundle_control_sha256(jsonb)"
        for statement in upgrade:
            conn.execute(statement)
        for statement in downgrade:
            conn.execute(statement)
        conn.commit()
