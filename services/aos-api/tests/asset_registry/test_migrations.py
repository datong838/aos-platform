"""M1 asset registry migration shape and PostgreSQL behavior tests."""
from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from aos_api.db import connect
from psycopg import errors, sql

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_registry.py"
TABLES = (
    "asset_bundle",
    "asset_bundle_version",
    "asset_bundle_dependency",
    "asset_bundle_artifact",
    "asset_bundle_evidence",
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("asset_registry_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _statements(module: ModuleType, operation: str) -> list[str]:
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        getattr(module, operation)()
    return statements


@contextmanager
def _isolated_registry(
    upgrade_sql: list[str],
) -> Iterator[tuple[str, object]]:
    schema = f"asset_registry_migration_{uuid.uuid4().hex}"
    created = False
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            created = True
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            for statement in upgrade_sql:
                conn.execute(statement)
            conn.commit()
        yield schema, connect
    except Exception as exc:
        if not created:
            pytest.skip(f"PG unavailable: {exc}")
        raise
    finally:
        if created:
            with connect() as cleanup:
                cleanup.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
                cleanup.commit()


def _set_search_path(conn: object, schema: str) -> None:
    conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))


def _assert_check_violation(conn: object, statement: str) -> None:
    savepoint = f"expected_failure_{uuid.uuid4().hex}"
    conn.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(savepoint)))
    with pytest.raises(errors.CheckViolation):
        conn.execute(statement)
    conn.execute(
        sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint))
    )
    conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(savepoint)))


def _seed_published_registry(conn: object) -> None:
    conn.execute(
        """
        INSERT INTO asset_bundle (
          bundle_pk, publisher, bundle_id, kind, display_name
        ) VALUES (
          '10000000-0000-0000-0000-000000000001',
          'aos', 'solution.example', 'SolutionPack', 'Example'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO asset_bundle_version (
          version_pk, bundle_pk, version, manifest_json, content_hash,
          signature, status, created_by
        ) VALUES (
          '20000000-0000-0000-0000-000000000001',
          '10000000-0000-0000-0000-000000000001',
          '1.0.0', '{"apiVersion":"aos.dev/v1alpha1"}',
          'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          '{"algorithm":"Ed25519"}', 'draft', 'publisher:aos'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO asset_bundle_dependency (
          version_pk, dependency_publisher, dependency_id,
          version_range, optional, ordinal
        ) VALUES (
          '20000000-0000-0000-0000-000000000001',
          'aos', 'domain.example', '>=1.0.0 <2.0.0', FALSE, 0
        )
        """
    )
    conn.execute(
        """
        INSERT INTO asset_bundle_artifact (
          version_pk, relative_path, artifact_ref, digest, size, media_type
        ) VALUES (
          '20000000-0000-0000-0000-000000000001',
          'bundle.yaml', 'bundle://solutions/example/bundle.yaml',
          'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
          128, 'application/yaml'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO asset_bundle_evidence (
          version_pk, evidence_type, artifact_ref, artifact_hash, status,
          observed_at, expires_at, updated_by
        ) VALUES (
          '20000000-0000-0000-0000-000000000001',
          'sbom', 'bundle://solutions/example/evidence/sbom.json',
          'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
          'pending', NOW(), NOW() + INTERVAL '30 days', 'publisher:aos'
        )
        """
    )
    conn.execute(
        """
        UPDATE asset_bundle_version
           SET status = 'validated', updated_at = updated_at + INTERVAL '1 second'
         WHERE version_pk = '20000000-0000-0000-0000-000000000001'
        """
    )
    conn.execute(
        """
        UPDATE asset_bundle_version
           SET status = 'published', updated_at = updated_at + INTERVAL '1 second'
         WHERE version_pk = '20000000-0000-0000-0000-000000000001'
        """
    )


def test_migration_shape_chain_and_fail_closed_downgrade() -> None:
    module = _load_migration()
    upgrade_sql = "\n".join(_statements(module, "upgrade"))
    downgrade_sql = "\n".join(_statements(module, "downgrade"))

    assert module.revision == "a93c7e1b4f20"
    assert module.down_revision == "228logicpublish"
    for table in TABLES:
        assert f"CREATE TABLE {table}" in upgrade_sql
    assert "UNIQUE (publisher, bundle_id)" in upgrade_sql
    assert "UNIQUE (bundle_pk, version)" in upgrade_sql
    assert "REFERENCES asset_bundle(bundle_pk) ON DELETE RESTRICT" in upgrade_sql
    assert upgrade_sql.count("REFERENCES asset_bundle_version(version_pk)") == 3
    assert "trg_asset_bundle_version_guard" in upgrade_sql
    assert "trg_asset_bundle_dependency_guard" in upgrade_sql
    assert "trg_asset_bundle_artifact_guard" in upgrade_sql
    assert "trg_asset_bundle_evidence_guard" in upgrade_sql
    assert "canonical tables are not empty" in downgrade_sql
    assert "DROP TABLE IF EXISTS" not in downgrade_sql


def test_published_rows_are_immutable_except_audited_lifecycle_updates() -> None:
    module = _load_migration()
    with (
        _isolated_registry(_statements(module, "upgrade")) as (schema, connect_fn),
        connect_fn() as conn,
    ):
        _set_search_path(conn, schema)
        _seed_published_registry(conn)

        _assert_check_violation(
            conn,
            """
            INSERT INTO asset_bundle_version (
              version_pk, bundle_pk, version, manifest_json, content_hash,
              signature, status, created_by
            ) VALUES (
              '20000000-0000-0000-0000-000000000002',
              '10000000-0000-0000-0000-000000000001',
              '2.0.0', '{}',
              'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
              '{"algorithm":"Ed25519"}', 'published', 'publisher:aos'
            )
            """,
        )
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle_version
               SET content_hash =
                 'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """,
        )
        _assert_check_violation(
            conn,
            """
            DELETE FROM asset_bundle_version
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """,
        )
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle_dependency SET version_range = '>=2.0.0'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """,
        )
        _assert_check_violation(
            conn,
            """
            DELETE FROM asset_bundle_artifact
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """,
        )
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle_evidence
               SET artifact_hash =
                 'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """,
        )
        conn.execute(
            """
            INSERT INTO asset_bundle_version (
              version_pk, bundle_pk, version, manifest_json, content_hash,
              status, created_by
            ) VALUES (
              '20000000-0000-0000-0000-000000000002',
              '10000000-0000-0000-0000-000000000001',
              '2.0.0', '{}',
              'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
              'draft', 'publisher:aos'
            )
            """
        )
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle_evidence
               SET version_pk = '20000000-0000-0000-0000-000000000002'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """,
        )
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle SET display_name = 'Overwritten'
             WHERE bundle_pk = '10000000-0000-0000-0000-000000000001'
            """,
        )

        conn.execute(
            """
            UPDATE asset_bundle_evidence
               SET status = 'valid',
                   updated_at = updated_at + INTERVAL '1 second',
                   updated_by = 'verifier:aos',
                   status_reason = 'signature and SBOM verified'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """
        )
        conn.execute(
            """
            UPDATE asset_bundle_evidence
               SET status = 'revoked',
                   revoked_at = NOW(),
                   updated_at = updated_at + INTERVAL '1 second',
                   updated_by = 'security:aos',
                   status_reason = 'publisher trust root revoked'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """
        )
        conn.execute(
            """
            UPDATE asset_bundle_version
               SET status = 'deprecated',
                   updated_at = updated_at + INTERVAL '1 second'
             WHERE version_pk = '20000000-0000-0000-0000-000000000001'
            """
        )
        row = conn.execute(
            """
            SELECT v.status AS version_status, e.status AS evidence_status
              FROM asset_bundle_version v
              JOIN asset_bundle_evidence e USING (version_pk)
             WHERE v.version_pk = '20000000-0000-0000-0000-000000000001'
            """
        ).fetchone()
        assert row["version_status"] == "deprecated"
        assert row["evidence_status"] == "revoked"
        conn.commit()


def test_downgrade_blocks_nonempty_canonical_tables() -> None:
    module = _load_migration()
    upgrade_sql = _statements(module, "upgrade")
    downgrade_sql = _statements(module, "downgrade")
    with (
        _isolated_registry(upgrade_sql) as (schema, connect_fn),
        connect_fn() as conn,
    ):
        _set_search_path(conn, schema)
        _seed_published_registry(conn)
        _assert_check_violation(conn, downgrade_sql[0])
        for table in TABLES:
            assert (
                conn.execute("SELECT to_regclass(%s) AS name", (table,)).fetchone()[
                    "name"
                ]
                == table
            )
        conn.rollback()


def test_empty_downgrade_and_reupgrade_round_trip() -> None:
    module = _load_migration()
    upgrade_sql = _statements(module, "upgrade")
    downgrade_sql = _statements(module, "downgrade")
    with (
        _isolated_registry(upgrade_sql) as (schema, connect_fn),
        connect_fn() as conn,
    ):
        _set_search_path(conn, schema)
        for statement in downgrade_sql:
            conn.execute(statement)
        for table in TABLES:
            assert (
                conn.execute(
                    "SELECT to_regclass(%s) AS name", (table,)
                ).fetchone()["name"]
                is None
            )

        for statement in upgrade_sql:
            conn.execute(statement)
        for table in TABLES:
            assert (
                conn.execute(
                    "SELECT to_regclass(%s) AS name", (table,)
                ).fetchone()["name"]
                == table
            )
        for statement in downgrade_sql:
            conn.execute(statement)
        conn.commit()
