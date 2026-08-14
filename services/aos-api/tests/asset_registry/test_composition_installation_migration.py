"""Real PostgreSQL tests for the M2 composition/installation migration."""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import IntegrityError, errors, sql
from psycopg.types.json import Jsonb

from aos_api.db import connect

API_ROOT = Path(__file__).resolve().parents[2]
BASE_MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
)
MIGRATION_PATH = API_ROOT / "alembic/versions/228asset1_composition_installation.py"
M2_TABLES = (
    "bundle_composition",
    "bundle_composition_lock",
    "bundle_installation",
    "bundle_installation_revision",
    "bundle_installation_decision",
    "bundle_installation_event",
    "bundle_installation_command",
)
ORG = "org-test"
PROJECT = "project-test"
COMPOSITION_PK = uuid.UUID("10000000-0000-0000-0000-000000000001")
COMPOSITION_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
INSTALLATION_PK = uuid.UUID("20000000-0000-0000-0000-000000000001")
INSTALLATION_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
DECISION_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
ZERO_HASH = "sha256:" + "0" * 64


def _load_migration(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_statements(
    path: Path,
    name: str,
    operation: str,
) -> list[str]:
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
        statements.extend(_migration_statements(path, f"m2_upgrade_{index}", "upgrade"))
    return statements


@contextmanager
def _isolated_m2_schema() -> Iterator[Callable[[], object]]:
    schema = f"bundle_control_migration_{uuid.uuid4().hex}"
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
        "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
        (Jsonb(value),),
    ).fetchone()["hash"]


def _lock_documents() -> tuple[dict, dict]:
    empty_diff = {
        "baseline": {},
        "target": {},
        "added": {},
        "removed": {},
        "unchanged": {},
    }
    lock_payload = {
        "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
        "resolverVersion": "aos-resolver/1.0.0",
        "request": {},
        "registrySnapshotHash": ZERO_HASH,
        "resolved": [],
        "edges": [],
        "capabilityProviders": [],
        "permissionDiff": empty_diff,
        "migrationPlan": empty_diff,
        "contributionDiff": empty_diff,
        "currentInstallationRef": None,
    }
    return empty_diff, lock_payload


def _insert_composition(conn: object) -> None:
    request = {"requested": []}
    snapshot = {
        "schemaVersion": "aos.dev/registry-snapshot/v1alpha1",
        "candidates": [],
    }
    conn.execute(
        """
        INSERT INTO bundle_composition (
          org_id, project_id, composition_pk, composition_id,
          request_json, request_hash,
          registry_snapshot_json, registry_snapshot_hash,
          current_installation_ref_json, current_installation_ref_hash,
          resolver_version, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL,
                  'aos-resolver/1.0.0', 'resolver:test')
        """,
        (
            ORG,
            PROJECT,
            COMPOSITION_PK,
            COMPOSITION_ID,
            Jsonb(request),
            _canonical_hash(conn, request),
            Jsonb(snapshot),
            _canonical_hash(conn, snapshot),
        ),
    )


def _insert_lock(conn: object) -> tuple[str, str]:
    _insert_composition(conn)
    diff, payload = _lock_documents()
    diff_hash = _canonical_hash(conn, diff)
    lock_hash = _canonical_hash(conn, payload)
    conn.execute(
        """
        INSERT INTO bundle_composition_lock (
          org_id, project_id, composition_pk, revision,
          lock_payload, lock_hash,
          permission_diff_json, permission_diff_hash,
          migration_plan_json, migration_plan_hash,
          contribution_diff_json, contribution_diff_hash, created_by
        ) VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s,
                  'resolver:test')
        """,
        (
            ORG,
            PROJECT,
            COMPOSITION_PK,
            Jsonb(payload),
            lock_hash,
            Jsonb(diff),
            diff_hash,
            Jsonb(diff),
            diff_hash,
            Jsonb(diff),
            diff_hash,
        ),
    )
    return lock_hash, diff_hash


def _insert_revision(
    conn: object,
    revision: int,
    state: str,
    lock_hash: str,
    diff_hash: str,
    *,
    decision_id: uuid.UUID | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO bundle_installation_revision (
          org_id, project_id, installation_pk, revision, parent_revision,
          state, composition_pk, lock_revision, lock_hash,
          permission_diff_hash, migration_plan_hash, contribution_diff_hash,
          overlay_revision, requested_by, decision_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s,
                  'overlay-v1', 'requester:test', %s)
        """,
        (
            ORG,
            PROJECT,
            INSTALLATION_PK,
            revision,
            revision - 1 if revision > 1 else None,
            state,
            COMPOSITION_PK,
            lock_hash,
            diff_hash,
            diff_hash,
            diff_hash,
            decision_id,
        ),
    )


def _insert_event(
    conn: object,
    revision: int,
    from_state: str | None,
    to_state: str,
) -> None:
    conn.execute(
        """
        INSERT INTO bundle_installation_event (
          org_id, project_id, installation_pk, sequence,
          from_revision, to_revision, from_state, to_state, actor
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'actor:test')
        """,
        (
            ORG,
            PROJECT,
            INSTALLATION_PK,
            revision,
            revision - 1 if revision > 1 else None,
            revision,
            from_state,
            to_state,
        ),
    )


def _insert_draft(conn: object) -> tuple[str, str]:
    lock_hash, diff_hash = _insert_lock(conn)
    conn.execute(
        """
        INSERT INTO bundle_installation (
          org_id, project_id, installation_pk, installation_id, display_name,
          current_revision, active_revision, previous_active_revision,
          etag_version, created_by
        ) VALUES (%s, %s, %s, %s, 'Test installation', 1, NULL, NULL, 1,
                  'requester:test')
        """,
        (ORG, PROJECT, INSTALLATION_PK, INSTALLATION_ID),
    )
    _insert_revision(conn, 1, "draft", lock_hash, diff_hash)
    _insert_event(conn, 1, None, "draft")
    return lock_hash, diff_hash


def _advance(
    conn: object,
    revision: int,
    from_state: str,
    to_state: str,
    lock_hash: str,
    diff_hash: str,
    *,
    decision_id: uuid.UUID | None = None,
    active_revision: int | None = None,
    previous_active_revision: int | None = None,
) -> None:
    _insert_revision(
        conn,
        revision,
        to_state,
        lock_hash,
        diff_hash,
        decision_id=decision_id,
    )
    _insert_event(conn, revision, from_state, to_state)
    conn.execute(
        """
        UPDATE bundle_installation
           SET current_revision = %s,
               active_revision = %s,
               previous_active_revision = %s,
               etag_version = %s,
               updated_at = updated_at + INTERVAL '1 second'
         WHERE org_id = %s AND project_id = %s
           AND installation_pk = %s
        """,
        (
            revision,
            active_revision,
            previous_active_revision,
            revision,
            ORG,
            PROJECT,
            INSTALLATION_PK,
        ),
    )


def test_migration_shape_and_single_head() -> None:
    module = _load_migration(MIGRATION_PATH, "m2_migration_shape")
    upgrade_sql = "\n".join(
        _migration_statements(MIGRATION_PATH, "m2_shape_upgrade", "upgrade")
    )
    downgrade_sql = "\n".join(
        _migration_statements(MIGRATION_PATH, "m2_shape_downgrade", "downgrade")
    )
    script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))

    assert module.revision == "228assetinstall"
    assert module.down_revision == "228assetevidence"
    assert len(script.get_heads()) == 1
    reachable = {
        revision.revision
        for revision in script.walk_revisions(base="base", head="heads")
    }
    assert "228assetintegration" in reachable
    for table in M2_TABLES:
        assert f"CREATE TABLE {table}" in upgrade_sql
    assert "COALESCE(current_installation_ref_hash, '')" in upgrade_sql
    assert "canonical_bundle_control_sha256" in upgrade_sql
    assert "DEFERRABLE INITIALLY DEFERRED" in upgrade_sql
    assert "canonical data exists" in downgrade_sql
    assert "DROP TABLE IF EXISTS" not in downgrade_sql


def test_lock_hash_dedupe_and_immutability_are_database_enforced() -> None:
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash, _ = _insert_lock(conn)
        conn.commit()

        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_composition (
              org_id, project_id, composition_pk, composition_id,
              request_json, request_hash,
              registry_snapshot_json, registry_snapshot_hash,
              resolver_version, created_by
            )
            SELECT org_id, project_id,
                   '10000000-0000-0000-0000-000000000010'::UUID,
                   '10000000-0000-0000-0000-000000000011'::UUID,
                   request_json, request_hash,
                   registry_snapshot_json, registry_snapshot_hash,
                   resolver_version, created_by
              FROM bundle_composition
            """,
            errors.UniqueViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_composition_lock (
              org_id, project_id, composition_pk, revision,
              lock_payload, lock_hash,
              permission_diff_json, permission_diff_hash,
              migration_plan_json, migration_plan_hash,
              contribution_diff_json, contribution_diff_hash, created_by
            )
            SELECT org_id, project_id, composition_pk, 2,
                   lock_payload,
                   'sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
                   permission_diff_json, permission_diff_hash,
                   migration_plan_json, migration_plan_hash,
                   contribution_diff_json, contribution_diff_hash, created_by
              FROM bundle_composition_lock
             WHERE revision = 1
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_composition_lock (
              org_id, project_id, composition_pk, revision,
              lock_payload, lock_hash,
              permission_diff_json, permission_diff_hash,
              migration_plan_json, migration_plan_hash,
              contribution_diff_json, contribution_diff_hash, created_by
            )
            SELECT org_id, project_id, composition_pk, 2,
                   lock_payload, lock_hash,
                   permission_diff_json,
                   'sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
                   migration_plan_json, migration_plan_hash,
                   contribution_diff_json, contribution_diff_hash, created_by
              FROM bundle_composition_lock
             WHERE revision = 1
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "UPDATE bundle_composition_lock SET created_by = 'attacker:test'",
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            f"DELETE FROM bundle_composition_lock WHERE lock_hash = '{lock_hash}'",
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "TRUNCATE bundle_composition_lock CASCADE",
            errors.CheckViolation,
        )


def test_tenant_json_state_and_event_evidence_constraints_fail_closed() -> None:
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash, diff_hash = _insert_draft(conn)
        conn.commit()

        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_composition (
              org_id, project_id, composition_pk, composition_id,
              request_json, request_hash,
              registry_snapshot_json, registry_snapshot_hash,
              resolver_version, created_by
            ) VALUES (
              'org-test', 'project-test',
              '10000000-0000-0000-0000-000000000020',
              '10000000-0000-0000-0000-000000000021',
              '[]',
              'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              '{}',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
              'aos-resolver/1.0.0', 'resolver:test'
            )
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_composition_lock (
              org_id, project_id, composition_pk, revision,
              lock_payload, lock_hash,
              permission_diff_json, permission_diff_hash,
              migration_plan_json, migration_plan_hash,
              contribution_diff_json, contribution_diff_hash, created_by
            )
            SELECT 'org-other', project_id, composition_pk, 2,
                   lock_payload, lock_hash,
                   permission_diff_json, permission_diff_hash,
                   migration_plan_json, migration_plan_hash,
                   contribution_diff_json, contribution_diff_hash, created_by
              FROM bundle_composition_lock
             WHERE revision = 1
            """,
            errors.ForeignKeyViolation,
        )
        _assert_integrity_violation(
            conn,
            f"""
            INSERT INTO bundle_installation_revision (
              org_id, project_id, installation_pk, revision, parent_revision,
              state, composition_pk, lock_revision, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash, overlay_revision, requested_by
            ) VALUES (
              '{ORG}', '{PROJECT}', '{INSTALLATION_PK}', 2, 1,
              'unknown', '{COMPOSITION_PK}', 1, '{lock_hash}',
              '{diff_hash}', '{diff_hash}', '{diff_hash}',
              'overlay-v1', 'requester:test'
            )
            """,
            errors.CheckViolation,
        )

        _advance(conn, 2, "draft", "submitted", lock_hash, diff_hash)
        conn.commit()
        conn.execute(
            """
            INSERT INTO bundle_installation_decision (
              org_id, project_id, decision_id, installation_pk,
              submitted_revision, decision, actor, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash
            ) VALUES (%s, %s, %s, %s, 2, 'approved', 'approver:test',
                      %s, %s, %s, %s)
            """,
            (
                ORG,
                PROJECT,
                DECISION_ID,
                INSTALLATION_PK,
                lock_hash,
                diff_hash,
                diff_hash,
                diff_hash,
            ),
        )
        _advance(
            conn,
            3,
            "submitted",
            "approved",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        conn.commit()
        evidence = {
            "type": "dry_apply",
            "evidenceRef": "evidence://dry-apply/1",
            "evidenceHash": ZERO_HASH,
            "status": "valid",
            "observedAt": "2026-08-03T00:00:00Z",
        }
        savepoint = sql.Identifier(f"bad_evidence_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(savepoint))
        _insert_revision(
            conn,
            4,
            "applied",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        with pytest.raises(errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO bundle_installation_event (
                  org_id, project_id, installation_pk, sequence,
                  from_revision, to_revision, from_state, to_state, actor,
                  evidence_json, evidence_hash
                ) VALUES (%s, %s, %s, 4, 3, 4, 'approved', 'applied',
                          'installer:test', %s,
                          'sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff')
                """,
                (ORG, PROJECT, INSTALLATION_PK, Jsonb(evidence)),
            )
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(savepoint))


def test_valid_immutable_installation_lifecycle_and_decision_lineage() -> None:
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash, diff_hash = _insert_draft(conn)
        conn.commit()

        _advance(conn, 2, "draft", "submitted", lock_hash, diff_hash)
        conn.commit()
        conn.execute(
            """
            INSERT INTO bundle_installation_decision (
              org_id, project_id, decision_id, installation_pk,
              submitted_revision, decision, actor, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash
            ) VALUES (%s, %s, %s, %s, 2, 'approved', 'approver:test',
                      %s, %s, %s, %s)
            """,
            (
                ORG,
                PROJECT,
                DECISION_ID,
                INSTALLATION_PK,
                lock_hash,
                diff_hash,
                diff_hash,
                diff_hash,
            ),
        )
        _advance(
            conn,
            3,
            "submitted",
            "approved",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        conn.commit()
        _advance(
            conn,
            4,
            "approved",
            "applied",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        conn.commit()
        _advance(
            conn,
            5,
            "applied",
            "active",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
            active_revision=5,
        )
        conn.commit()
        _advance(
            conn,
            6,
            "active",
            "rolled_back",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT current_revision, active_revision,
                   previous_active_revision, etag_version
              FROM bundle_installation
            """
        ).fetchone()
        assert row == {
            "current_revision": 6,
            "active_revision": None,
            "previous_active_revision": None,
            "etag_version": 6,
        }
        revisions = conn.execute(
            """
            SELECT revision, state, decision_id
              FROM bundle_installation_revision
             ORDER BY revision
            """
        ).fetchall()
        assert [item["state"] for item in revisions] == [
            "draft",
            "submitted",
            "approved",
            "applied",
            "active",
            "rolled_back",
        ]
        assert all(item["decision_id"] == DECISION_ID for item in revisions[2:])


def test_active_pointer_history_and_rollback_are_database_enforced() -> None:
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash, diff_hash = _insert_draft(conn)
        conn.commit()

        _advance(conn, 2, "draft", "submitted", lock_hash, diff_hash)
        conn.commit()
        conn.execute(
            """
            INSERT INTO bundle_installation_decision (
              org_id, project_id, decision_id, installation_pk,
              submitted_revision, decision, actor, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash
            ) VALUES (%s, %s, %s, %s, 2, 'approved', 'approver:test',
                      %s, %s, %s, %s)
            """,
            (
                ORG,
                PROJECT,
                DECISION_ID,
                INSTALLATION_PK,
                lock_hash,
                diff_hash,
                diff_hash,
                diff_hash,
            ),
        )
        _advance(
            conn,
            3,
            "submitted",
            "approved",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        conn.commit()
        _advance(
            conn,
            4,
            "approved",
            "applied",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
        )
        conn.commit()
        active_savepoint = sql.Identifier(f"bad_active_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(active_savepoint))
        with pytest.raises(errors.CheckViolation):
            _advance(
                conn,
                5,
                "applied",
                "active",
                lock_hash,
                diff_hash,
                decision_id=DECISION_ID,
                active_revision=5,
                previous_active_revision=5,
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(active_savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(active_savepoint))
        conn.execute("SET CONSTRAINTS ALL DEFERRED")

        _advance(
            conn,
            5,
            "applied",
            "active",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
            active_revision=5,
        )
        conn.commit()

        # M2 intentionally has no upgrade action, so seed a second active
        # revision solely to exercise the pointer invariant against a
        # future-compatible, non-null previous active history. The production
        # transition guard is restored before consistency checks are forced.
        conn.execute(
            """
            ALTER TABLE bundle_installation_revision
            DISABLE TRIGGER trg_bundle_installation_revision_insert_guard
            """
        )
        try:
            _advance(
                conn,
                6,
                "active",
                "active",
                lock_hash,
                diff_hash,
                decision_id=DECISION_ID,
                active_revision=6,
                previous_active_revision=5,
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        finally:
            conn.execute(
                """
                ALTER TABLE bundle_installation_revision
                ENABLE TRIGGER trg_bundle_installation_revision_insert_guard
                """
            )
        conn.execute("SET CONSTRAINTS ALL DEFERRED")
        conn.commit()

        rollback_savepoint = sql.Identifier(f"bad_rollback_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(rollback_savepoint))
        with pytest.raises(errors.CheckViolation):
            _advance(
                conn,
                7,
                "active",
                "rolled_back",
                lock_hash,
                diff_hash,
                decision_id=DECISION_ID,
                active_revision=7,
                previous_active_revision=7,
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(rollback_savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(rollback_savepoint))
        conn.execute("SET CONSTRAINTS ALL DEFERRED")

        _advance(
            conn,
            7,
            "active",
            "rolled_back",
            lock_hash,
            diff_hash,
            decision_id=DECISION_ID,
            active_revision=5,
            previous_active_revision=5,
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT current_revision, active_revision,
                   previous_active_revision, etag_version
              FROM bundle_installation
            """
        ).fetchone()
        assert row == {
            "current_revision": 7,
            "active_revision": 5,
            "previous_active_revision": 5,
            "etag_version": 7,
        }


def test_revision_decision_event_and_pointer_bypasses_fail_closed() -> None:
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        lock_hash, diff_hash = _insert_draft(conn)
        conn.commit()

        _assert_integrity_violation(
            conn,
            """
            UPDATE bundle_installation
               SET current_revision = 2, etag_version = 2,
                   updated_at = updated_at + INTERVAL '1 second'
            """,
            IntegrityError,
            defer_check=True,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_installation_revision (
              org_id, project_id, installation_pk, revision, parent_revision,
              state, composition_pk, lock_revision, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash, overlay_revision, requested_by
            ) VALUES (
              'org-test', 'project-test',
              '20000000-0000-0000-0000-000000000001', 2, 1,
              'active', '10000000-0000-0000-0000-000000000001', 1,
              'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
              'overlay-v1', 'requester:test'
            )
            """,
            errors.CheckViolation,
        )

        _advance(conn, 2, "draft", "submitted", lock_hash, diff_hash)
        conn.commit()
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_installation_decision (
              org_id, project_id, decision_id, installation_pk,
              submitted_revision, decision, actor, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash
            ) VALUES (
              'org-test', 'project-test',
              '30000000-0000-0000-0000-000000000010',
              '20000000-0000-0000-0000-000000000001', 2,
              'approved', 'requester:test',
              'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
              'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
            )
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            UPDATE bundle_installation_revision SET state = 'active'
             WHERE revision = 2
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            """
            INSERT INTO bundle_installation_event (
              org_id, project_id, installation_pk, sequence,
              from_revision, to_revision, from_state, to_state, actor
            ) VALUES (
              'org-test', 'project-test',
              '20000000-0000-0000-0000-000000000001',
              4, 2, 2, 'submitted', 'submitted', 'attacker:test'
            )
            """,
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "TRUNCATE bundle_installation_event CASCADE",
            errors.CheckViolation,
        )


def test_command_constraints_tenant_scope_and_immutability() -> None:
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        valid_insert = """
            INSERT INTO bundle_installation_command (
              org_id, project_id, operation, idempotency_key, subject,
              request_hash, status_code, response_json, response_etag
            ) VALUES (
              'org-test', 'project-test', 'resolve', 'request-1', 'user:test',
              'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              201, '{}', NULL
            )
        """
        conn.execute(valid_insert)
        conn.execute(valid_insert.replace("'org-test'", "'org-other'", 1))
        conn.commit()

        _assert_integrity_violation(
            conn,
            valid_insert,
            errors.UniqueViolation,
        )
        _assert_integrity_violation(
            conn,
            valid_insert.replace("201", "409"),
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "UPDATE bundle_installation_command SET status_code = 200",
            errors.CheckViolation,
        )
        _assert_integrity_violation(
            conn,
            "TRUNCATE bundle_installation_command",
            errors.CheckViolation,
        )


def test_nonempty_downgrade_blocks_and_empty_up_down_up_succeeds() -> None:
    downgrade = _migration_statements(
        MIGRATION_PATH,
        "m2_downgrade_round_trip",
        "downgrade",
    )
    upgrade = _migration_statements(
        MIGRATION_PATH,
        "m2_reupgrade_round_trip",
        "upgrade",
    )
    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        _insert_lock(conn)
        conn.commit()
        _assert_integrity_violation(
            conn,
            downgrade[0],
            errors.CheckViolation,
        )
        assert (
            conn.execute(
                "SELECT to_regclass('bundle_composition_lock') AS table_name"
            ).fetchone()["table_name"]
            == "bundle_composition_lock"
        )

    with _isolated_m2_schema() as scoped_connect, scoped_connect() as conn:
        for statement in downgrade:
            conn.execute(statement)
        for table in M2_TABLES:
            assert (
                conn.execute(
                    "SELECT to_regclass(%s) AS table_name", (table,)
                ).fetchone()["table_name"]
                is None
            )
        assert (
            conn.execute(
                "SELECT to_regprocedure("
                "'canonical_asset_registry_jsonb(jsonb)') AS function"
            ).fetchone()["function"]
            == "canonical_asset_registry_jsonb(jsonb)"
        )

        for statement in upgrade:
            conn.execute(statement)
        for table in M2_TABLES:
            assert (
                conn.execute(
                    "SELECT to_regclass(%s) AS table_name", (table,)
                ).fetchone()["table_name"]
                == table
            )
        for statement in downgrade:
            conn.execute(statement)
        conn.commit()
