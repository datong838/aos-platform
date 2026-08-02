"""PostgreSQL evidence tests for the canonical Registry store."""

from __future__ import annotations

import importlib.util
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from types import ModuleType
from unittest.mock import patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import errors, sql

from aos_api.asset_registry.contracts import (
    BundleVersionStatus,
    LoadedBundle,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    ManifestInvalidError,
    RevisionConflictError,
    VersionInvalidError,
)
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.db import connect

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_registry.py"
SECURITY_MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_security.py"


def _load_migration(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements() -> list[str]:
    statements: list[str] = []
    for path, name in (
        (MIGRATION_PATH, "registry_store_migration"),
        (SECURITY_MIGRATION_PATH, "registry_store_security_migration"),
    ):
        module = _load_migration(path, name)
        with patch.object(module.op, "execute", statements.append):
            module.upgrade()
    return statements


def _migration_statements(
    path: Path,
    name: str,
    operation: str,
) -> list[str]:
    statements: list[str] = []
    module = _load_migration(path, name)
    with patch.object(module.op, "execute", statements.append):
        getattr(module, operation)()
    return statements


@contextmanager
def _isolated_schema(statements: list[str]):
    schema = f"asset_registry_security_{uuid.uuid4().hex}"
    with connect() as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for statement in statements:
            conn.execute(statement)
        conn.commit()

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
        with connect() as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            conn.commit()


@pytest.fixture()
def registry_scope():
    schema = f"asset_registry_store_{uuid.uuid4().hex}"
    created = False
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            created = True
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            for statement in _upgrade_statements():
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
        yield PostgresRegistryStore(scoped_connect), scoped_connect
    finally:
        with connect() as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            conn.commit()


def _manifest(
    *,
    publisher: str = "aos",
    bundle_id: str = "solution.example",
    version: str = "1.0.0",
) -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": bundle_id,
            "version": version,
            "displayName": "Example Solution",
            "publisher": publisher,
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [{"id": "domain.orders", "version": ">=1.0.0 <2.0.0"}],
            "optionalDependencies": [
                {
                    "id": "plugin.insights",
                    "version": "^1.1.0",
                    "publisher": "partner",
                }
            ],
            "conflicts": [],
            "exports": {
                "ontology": [],
                "links": [],
                "metrics": [],
                "agents": [],
                "logic": [],
                "workshops": [],
                "evals": [],
                "policies": [],
                "connectors": [],
                "schemas": [],
                "mappings": [],
                "backend": [],
                "ui": [],
            },
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {"plan": None, "downgradePolicy": "retain-canonical"},
            "preflight": None,
            "regression": None,
            "rollback": None,
        },
    }


def _loaded_bundle(
    *,
    publisher: str = "aos",
    bundle_id: str = "solution.example",
    version: str = "1.0.0",
) -> LoadedBundle:
    now = datetime.now(UTC)
    return LoadedBundle.model_validate(
        {
            "sourceRef": f"bundle://fixtures/{publisher}/{bundle_id}",
            "manifest": _manifest(
                publisher=publisher, bundle_id=bundle_id, version=version
            ),
            "artifacts": [
                {
                    "relativePath": "bundle.yaml",
                    "artifactRef": (
                        f"bundle://fixtures/{publisher}/{bundle_id}/bundle.yaml"
                    ),
                    "digest": "sha256:" + "a" * 64,
                    "size": 128,
                    "mediaType": "application/yaml",
                }
            ],
            "evidence": [
                {
                    "type": "manifest_validation",
                    "artifactRef": (
                        f"bundle://fixtures/{publisher}/{bundle_id}/evidence.json"
                    ),
                    "artifactHash": "sha256:" + "b" * 64,
                    "status": "valid",
                    "observedAt": now,
                    "expiresAt": now + timedelta(hours=1),
                    "revokedAt": None,
                    "metadata": {"validator": "registry-test"},
                }
            ],
            "contentHash": "sha256:" + "c" * 64,
            "signature": {
                "algorithm": "Ed25519",
                "keyId": "test-key",
                "signature": "base64-signature",
                "signedAt": now,
            },
            "loadedAt": now,
        }
    )


def _create_bundle(
    store: PostgresRegistryStore,
    *,
    publisher: str = "aos",
    bundle_id: str = "solution.example",
    display_name: str = "Example Solution",
) -> dict:
    return store.create_bundle(
        publisher,
        bundle_id,
        "SolutionPack",
        display_name,
        "publisher:test",
    )


def _assert_check_violation(conn, statement: str) -> None:
    name = f"expected_failure_{uuid.uuid4().hex}"
    conn.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(name)))
    with pytest.raises(errors.CheckViolation):
        conn.execute(statement)
    conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(name)))
    conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(name)))


def test_bundle_lookup_is_deterministic_and_ambiguous_ids_fail_closed(
    registry_scope,
) -> None:
    store, scoped_connect = registry_scope
    first = _create_bundle(store, publisher="aos", bundle_id="solution.shared")
    _create_bundle(store, publisher="partner", bundle_id="solution.shared")
    injected_name = "Robert'); DROP TABLE asset_bundle;--"
    _create_bundle(
        store,
        publisher="aos",
        bundle_id="solution.inject-safe",
        display_name=injected_name,
    )

    assert first["publisher"] == "aos"
    assert store.get_bundle("solution.shared", "partner")["publisher"] == "partner"
    with pytest.raises(RevisionConflictError, match="ambiguous"):
        store.get_bundle("solution.shared")
    with pytest.raises(RevisionConflictError, match="already exists"):
        _create_bundle(store, publisher="aos", bundle_id="solution.shared")
    with pytest.raises(ManifestInvalidError, match="identity contract"):
        _create_bundle(store, publisher="bad publisher", bundle_id="solution.bad")
    with pytest.raises(AssetNotFoundError):
        store.get_bundle("solution.shared' OR TRUE --", "aos")

    restarted = PostgresRegistryStore(scoped_connect)
    rows = restarted.list_bundles()
    assert [(row["publisher"], row["bundleId"]) for row in rows] == [
        ("aos", "solution.inject-safe"),
        ("aos", "solution.shared"),
        ("partner", "solution.shared"),
    ]
    assert (
        restarted.get_bundle("solution.inject-safe", "aos")["displayName"]
        == injected_name
    )
    with scoped_connect() as conn:
        assert (
            conn.execute("SELECT count(*) AS count FROM asset_bundle").fetchone()[
                "count"
            ]
            == 3
        )

    _create_bundle(store, publisher="solo", bundle_id="solution.transition")
    _create_bundle(store, publisher="other", bundle_id="solution.transition")
    store.create_version(
        _loaded_bundle(publisher="solo", bundle_id="solution.transition"),
        "publisher:solo",
    )
    with pytest.raises(RevisionConflictError, match="ambiguous"):
        store.transition_version(
            "solution.transition",
            "1.0.0",
            {"draft"},
            "validated",
            "validator:test",
        )
    transitioned = store.transition_version(
        "solution.transition",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
        publisher="solo",
    )
    assert transitioned["publisher"] == "solo"
    assert transitioned["status"] == "validated"


def test_version_projection_is_atomic_json_friendly_and_restart_durable(
    registry_scope,
) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store)
    loaded = _loaded_bundle()

    created = store.create_version(loaded, "publisher:test")
    assert set(created) == {
        "publisher",
        "bundleId",
        "kind",
        "displayName",
        "version",
        "manifest",
        "contentHash",
        "signature",
        "status",
        "createdBy",
        "createdAt",
        "updatedAt",
        "dependencies",
        "artifacts",
        "evidence",
        "lifecycleEvents",
    }
    assert created["lifecycleEvents"] == []
    assert created["status"] == "draft"
    assert created["manifest"]["metadata"]["displayName"] == "Example Solution"
    assert [item["optional"] for item in created["dependencies"]] == [False, True]
    assert created["artifacts"][0]["relativePath"] == "bundle.yaml"
    assert created["evidence"][0]["observedAt"].endswith("+00:00")
    json.dumps(created)

    restarted = PostgresRegistryStore(scoped_connect)
    assert restarted.get_version("solution.example", "1.0.0", "aos") == created
    assert restarted.get_bundle("solution.example", "aos")["versions"] == [
        {
            key: created[key]
            for key in (
                "version",
                "contentHash",
                "signature",
                "status",
                "createdBy",
                "createdAt",
                "updatedAt",
            )
        }
    ]
    with scoped_connect() as conn:
        row = conn.execute("SELECT updated_by FROM asset_bundle_evidence").fetchone()
        assert row["updated_by"] == "publisher:test"

    with pytest.raises(RevisionConflictError, match="already exists"):
        restarted.create_version(loaded, "publisher:test")


def test_projection_failure_rolls_back_version_and_all_children(registry_scope) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store)
    loaded = _loaded_bundle()

    class FailOnEvidence:
        def __init__(self, conn) -> None:
            self._conn = conn

        def execute(self, statement, params=None):
            if "INSERT INTO asset_bundle_evidence" in str(statement):
                raise RuntimeError("injected evidence persistence failure")
            return self._conn.execute(statement, params)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    @contextmanager
    def failing_connect():
        with scoped_connect() as conn:
            yield FailOnEvidence(conn)

    failing_store = PostgresRegistryStore(failing_connect)
    with pytest.raises(RuntimeError, match="injected evidence"):
        failing_store.create_version(loaded, "publisher:test")

    with scoped_connect() as conn:
        counts = {
            table: conn.execute(f"SELECT count(*) AS count FROM {table}").fetchone()[
                "count"
            ]
            for table in (
                "asset_bundle_version",
                "asset_bundle_dependency",
                "asset_bundle_artifact",
                "asset_bundle_evidence",
            )
        }
    assert counts == {
        "asset_bundle_version": 0,
        "asset_bundle_dependency": 0,
        "asset_bundle_artifact": 0,
        "asset_bundle_evidence": 0,
    }


def test_transition_uses_expected_status_and_database_immutability_guard(
    registry_scope,
) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store, bundle_id="solution.lifecycle")
    store.create_version(
        _loaded_bundle(bundle_id="solution.lifecycle"), "publisher:test"
    )

    validated = store.transition_version(
        "solution.lifecycle",
        "1.0.0",
        {BundleVersionStatus.DRAFT},
        BundleVersionStatus.VALIDATED,
        "validator:test",
        "all validation evidence passed",
    )
    assert validated["status"] == "validated"
    published = store.transition_version(
        "solution.lifecycle",
        "1.0.0",
        {"validated"},
        "published",
        "publisher:test",
    )
    assert published["status"] == "published"

    with pytest.raises(RevisionConflictError, match="status changed"):
        store.transition_version(
            "solution.lifecycle",
            "1.0.0",
            {"draft"},
            "validated",
            "validator:test",
        )
    with pytest.raises(VersionInvalidError, match="not allowed"):
        store.transition_version(
            "solution.lifecycle",
            "1.0.0",
            {"published"},
            "rejected",
            "publisher:test",
        )

    with scoped_connect() as conn:
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle_version
               SET content_hash =
                 'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'
             WHERE version = '1.0.0'
            """,
        )
        conn.rollback()

    deprecated = store.transition_version(
        "solution.lifecycle",
        "1.0.0",
        {"published"},
        "deprecated",
        "publisher:test",
        "superseded by a new bundle version",
    )
    assert deprecated["status"] == "deprecated"
    assert store.get_version("solution.lifecycle", "1.0.0")["status"] == "deprecated"

    with scoped_connect() as conn:
        _assert_check_violation(
            conn,
            "DELETE FROM asset_bundle_version WHERE version = '1.0.0'",
        )
        conn.rollback()


def test_security_migration_is_the_single_head_with_expected_parent() -> None:
    migration = _load_migration(
        SECURITY_MIGRATION_PATH,
        "registry_security_revision_contract",
    )
    script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))

    assert migration.revision == "228assetsecurity"
    assert migration.down_revision == "a93c7e1b4f20"
    assert script.get_heads() == ["228assetsecurity"]


def test_security_upgrade_backfills_validated_published_and_terminal_chains() -> None:
    base_statements = _migration_statements(
        MIGRATION_PATH,
        "registry_security_base_upgrade",
        "upgrade",
    )
    security_statements = _migration_statements(
        SECURITY_MIGRATION_PATH,
        "registry_security_upgrade",
        "upgrade",
    )
    expected_chains = {
        "draft": [],
        "validated": [("draft", "validated")],
        "published": [("draft", "validated"), ("validated", "published")],
        "deprecated": [
            ("draft", "validated"),
            ("validated", "published"),
            ("published", "deprecated"),
        ],
        "revoked": [
            ("draft", "validated"),
            ("validated", "published"),
            ("published", "revoked"),
        ],
        "rejected": [("draft", "rejected")],
    }
    transition_paths = {
        "draft": [],
        "validated": ["validated"],
        "published": ["validated", "published"],
        "deprecated": ["validated", "published", "deprecated"],
        "revoked": ["validated", "published", "revoked"],
        "rejected": ["rejected"],
    }

    with _isolated_schema(base_statements) as scoped_connect:
        version_keys: dict[str, uuid.UUID] = {}
        with scoped_connect() as conn:
            bundle_pk = uuid.uuid4()
            conn.execute(
                """
                INSERT INTO asset_bundle (
                  bundle_pk, publisher, bundle_id, kind, display_name
                ) VALUES (%s, 'aos', 'solution.legacy', 'SolutionPack', 'Legacy')
                """,
                (bundle_pk,),
            )
            for ordinal, (status, path) in enumerate(transition_paths.items()):
                version_pk = uuid.uuid4()
                version_keys[status] = version_pk
                conn.execute(
                    """
                    INSERT INTO asset_bundle_version (
                      version_pk, bundle_pk, version, manifest_json,
                      content_hash, signature, created_by
                    ) VALUES (%s, %s, %s, '{}'::JSONB, %s, '{}'::JSONB, 'legacy')
                    """,
                    (
                        version_pk,
                        bundle_pk,
                        f"1.0.{ordinal}",
                        "sha256:" + f"{ordinal:x}" * 64,
                    ),
                )
                for next_status in path:
                    conn.execute(
                        """
                        UPDATE asset_bundle_version
                           SET status = %s, updated_at = NOW()
                         WHERE version_pk = %s
                        """,
                        (next_status, version_pk),
                    )
            for statement in security_statements:
                conn.execute(statement)
            conn.commit()

        with scoped_connect() as conn:
            for status, version_pk in version_keys.items():
                rows = conn.execute(
                    """
                    SELECT sequence, from_status, to_status, actor,
                           reason, evidence_revision
                      FROM asset_bundle_version_event
                     WHERE version_pk = %s
                     ORDER BY sequence
                    """,
                    (version_pk,),
                ).fetchall()
                assert [
                    (row["from_status"], row["to_status"]) for row in rows
                ] == expected_chains[status]
                assert [row["sequence"] for row in rows] == list(
                    range(1, len(rows) + 1)
                )
                assert all(row["actor"] == "system:migration" for row in rows)
                assert all(
                    row["reason"]
                    == (
                        "backfilled by 228assetsecurity; "
                        "historical evidence unavailable"
                    )
                    for row in rows
                )
                assert all(
                    row["evidence_revision"] == "sha256:" + "0" * 64
                    for row in rows
                )


def test_security_event_log_rejects_all_direct_tampering(registry_scope) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store, bundle_id="solution.audit-guard")
    store.create_version(
        _loaded_bundle(bundle_id="solution.audit-guard"),
        "publisher:test",
    )
    store.transition_version(
        "solution.audit-guard",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
    )

    with scoped_connect() as conn:
        version_pk = conn.execute(
            "SELECT version_pk FROM asset_bundle_version"
        ).fetchone()["version_pk"]
        _assert_check_violation(
            conn,
            "UPDATE asset_bundle_version_event SET actor = 'attacker'",
        )
        _assert_check_violation(conn, "DELETE FROM asset_bundle_version_event")
        _assert_check_violation(conn, "TRUNCATE asset_bundle_version_event")

        forged_events = (
            (3, "validated", "rejected"),
            (2, "draft", "validated"),
            (2, "validated", "rejected"),
        )
        for sequence, from_status, to_status in forged_events:
            savepoint = f"forged_event_{sequence}_{to_status}"
            conn.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(savepoint)))
            with pytest.raises(errors.CheckViolation):
                conn.execute(
                    """
                    INSERT INTO asset_bundle_version_event (
                      event_pk, version_pk, sequence, from_status, to_status,
                      actor, evidence_revision
                    ) VALUES (%s, %s, %s, %s, %s, 'attacker', %s)
                    """,
                    (
                        uuid.uuid4(),
                        version_pk,
                        sequence,
                        from_status,
                        to_status,
                        "sha256:" + "f" * 64,
                    ),
                )
            conn.execute(
                sql.SQL("ROLLBACK TO SAVEPOINT {}").format(
                    sql.Identifier(savepoint)
                )
            )
            conn.execute(
                sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(savepoint))
            )

        assert (
            conn.execute(
                "SELECT count(*) AS count FROM asset_bundle_version_event"
            ).fetchone()["count"]
            == 1
        )


def test_store_transition_events_are_continuous_and_restart_durable(
    registry_scope,
) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store, bundle_id="solution.audit-durable")
    store.create_version(
        _loaded_bundle(bundle_id="solution.audit-durable"),
        "publisher:test",
    )

    validated = store.transition_version(
        "solution.audit-durable",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
        "validation passed",
    )
    assert [event["sequence"] for event in validated["lifecycleEvents"]] == [1]
    published = store.transition_version(
        "solution.audit-durable",
        "1.0.0",
        {"validated"},
        "published",
        "publisher:test",
        "release approved",
    )

    events = published["lifecycleEvents"]
    assert [event["sequence"] for event in events] == [1, 2]
    assert [
        (event["fromStatus"], event["toStatus"]) for event in events
    ] == [("draft", "validated"), ("validated", "published")]
    assert [event["actor"] for event in events] == [
        "validator:test",
        "publisher:test",
    ]
    assert all(
        event["evidenceRevision"].startswith("sha256:")
        and event["evidenceRevision"] != "sha256:" + "0" * 64
        for event in events
    )

    restarted = PostgresRegistryStore(scoped_connect)
    assert restarted.get_version(
        "solution.audit-durable", "1.0.0", "aos"
    )["lifecycleEvents"] == events


def test_concurrent_publish_allows_exactly_one_transition(registry_scope) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store, bundle_id="solution.concurrent")
    store.create_version(
        _loaded_bundle(bundle_id="solution.concurrent"),
        "publisher:test",
    )
    store.transition_version(
        "solution.concurrent",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
    )
    barrier = Barrier(2)

    def publish_once(worker: int) -> str:
        barrier.wait()
        try:
            store.transition_version(
                "solution.concurrent",
                "1.0.0",
                {"validated"},
                "published",
                f"publisher:worker-{worker}",
            )
        except RevisionConflictError:
            return "conflict"
        return "published"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(publish_once, range(2)))

    assert sorted(outcomes) == ["conflict", "published"]
    restarted = PostgresRegistryStore(scoped_connect)
    record = restarted.get_version("solution.concurrent", "1.0.0", "aos")
    assert record["status"] == "published"
    assert [event["sequence"] for event in record["lifecycleEvents"]] == [1, 2]
    assert [event["toStatus"] for event in record["lifecycleEvents"]] == [
        "validated",
        "published",
    ]


def test_security_downgrade_blocks_nonempty_log_and_allows_empty_log(
    registry_scope,
) -> None:
    store, scoped_connect = registry_scope
    downgrade_statements = _migration_statements(
        SECURITY_MIGRATION_PATH,
        "registry_security_downgrade_nonempty",
        "downgrade",
    )
    _create_bundle(store, bundle_id="solution.downgrade-blocked")
    store.create_version(
        _loaded_bundle(bundle_id="solution.downgrade-blocked"),
        "publisher:test",
    )
    store.transition_version(
        "solution.downgrade-blocked",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
    )
    with scoped_connect() as conn:
        with pytest.raises(errors.CheckViolation):
            for statement in downgrade_statements:
                conn.execute(statement)
        conn.rollback()
        assert conn.execute(
            "SELECT to_regclass('asset_bundle_version_event') AS relation"
        ).fetchone()["relation"] == "asset_bundle_version_event"

    with (
        _isolated_schema(_upgrade_statements()) as empty_scoped_connect,
        empty_scoped_connect() as conn,
    ):
        for statement in _migration_statements(
            SECURITY_MIGRATION_PATH,
            "registry_security_downgrade_empty",
            "downgrade",
        ):
            conn.execute(statement)
        conn.commit()
        assert conn.execute(
            "SELECT to_regclass('asset_bundle_version_event') AS relation"
        ).fetchone()["relation"] is None
        assert conn.execute(
            "SELECT to_regclass('asset_bundle_version') AS relation"
        ).fetchone()["relation"] == "asset_bundle_version"


def test_status_transition_requires_matching_event_at_commit(registry_scope) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store, bundle_id="solution.deferred-audit")
    store.create_version(
        _loaded_bundle(bundle_id="solution.deferred-audit"),
        "publisher:test",
    )

    with scoped_connect() as conn:
        version_pk = conn.execute(
            "SELECT version_pk FROM asset_bundle_version"
        ).fetchone()["version_pk"]
        conn.execute(
            "UPDATE asset_bundle_version SET status = 'validated' "
            "WHERE version_pk = %s",
            (version_pk,),
        )
        with pytest.raises(errors.CheckViolation, match="requires a lifecycle event"):
            conn.commit()
        conn.rollback()

    with scoped_connect() as conn:
        row = conn.execute(
            "SELECT status FROM asset_bundle_version WHERE version_pk = %s",
            (version_pk,),
        ).fetchone()
        assert row["status"] == "draft"
        assert conn.execute(
            "SELECT count(*) AS count FROM asset_bundle_version_event"
        ).fetchone()["count"] == 0

        conn.execute(
            "UPDATE asset_bundle_version SET status = 'validated' "
            "WHERE version_pk = %s",
            (version_pk,),
        )
        conn.execute(
            """
            INSERT INTO asset_bundle_version_event (
              event_pk, version_pk, sequence, from_status, to_status,
              actor, reason, evidence_revision
            ) VALUES (%s, %s, 1, 'draft', 'validated',
                      'validator:sql', 'atomic transition', %s)
            """,
            (uuid.uuid4(), version_pk, "sha256:" + "e" * 64),
        )
        conn.commit()

    restarted = PostgresRegistryStore(scoped_connect)
    record = restarted.get_version("solution.deferred-audit", "1.0.0", "aos")
    assert record["status"] == "validated"
    assert [
        (event["sequence"], event["fromStatus"], event["toStatus"])
        for event in record["lifecycleEvents"]
    ] == [(1, "draft", "validated")]


def _insert_phantom_projection(conn, table: str, version_pk: uuid.UUID) -> None:
    if table == "asset_bundle_dependency":
        conn.execute(
            """
            INSERT INTO asset_bundle_dependency (
              version_pk, dependency_publisher, dependency_id,
              version_range, optional, ordinal
            ) VALUES (%s, 'attacker', 'domain.phantom', '>=2.0.0', FALSE, 99)
            """,
            (version_pk,),
        )
        return
    if table == "asset_bundle_artifact":
        conn.execute(
            """
            INSERT INTO asset_bundle_artifact (
              version_pk, relative_path, artifact_ref, digest, size, media_type
            ) VALUES (%s, 'phantom.json', 'bundle://attacker/phantom.json',
                      %s, 1, 'application/json')
            """,
            (version_pk, "sha256:" + "f" * 64),
        )
        return
    assert table == "asset_bundle_evidence"
    conn.execute(
        """
        INSERT INTO asset_bundle_evidence (
          version_pk, evidence_type, artifact_ref, artifact_hash, status,
          observed_at, metadata, updated_by
        ) VALUES (%s, 'phantom', 'bundle://attacker/evidence.json', %s,
                  'valid', NOW(), '{}'::JSONB, 'attacker')
        """,
        (version_pk, "sha256:" + "d" * 64),
    )


@pytest.mark.parametrize(
    "table",
    [
        "asset_bundle_dependency",
        "asset_bundle_artifact",
        "asset_bundle_evidence",
    ],
)
def test_projection_insert_cannot_land_after_concurrent_publish(
    registry_scope,
    table: str,
) -> None:
    store, scoped_connect = registry_scope
    bundle_id = f"solution.concurrent-{table.removeprefix('asset_bundle_')}"
    _create_bundle(store, bundle_id=bundle_id)
    store.create_version(
        _loaded_bundle(bundle_id=bundle_id),
        "publisher:test",
    )
    store.transition_version(
        bundle_id,
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
    )
    with scoped_connect() as conn:
        version_pk = conn.execute(
            "SELECT version_pk FROM asset_bundle_version"
        ).fetchone()["version_pk"]
        count_before = conn.execute(
            sql.SQL("SELECT count(*) AS count FROM {}").format(
                sql.Identifier(table)
            )
        ).fetchone()["count"]

    publish_has_lock = Event()
    allow_publish = Event()
    insert_started = Event()

    def hold_publish(_record: dict) -> None:
        publish_has_lock.set()
        assert allow_publish.wait(timeout=5)

    def publish() -> dict:
        return store.transition_version(
            bundle_id,
            "1.0.0",
            {"validated"},
            "published",
            "publisher:test",
            precondition=hold_publish,
        )

    def insert_projection() -> None:
        with scoped_connect() as conn:
            insert_started.set()
            _insert_phantom_projection(conn, table, version_pk)
            conn.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        publish_future = executor.submit(publish)
        assert publish_has_lock.wait(timeout=5)
        insert_future = executor.submit(insert_projection)
        assert insert_started.wait(timeout=5)
        allow_publish.set()
        published = publish_future.result(timeout=5)
        with pytest.raises(errors.CheckViolation, match="published asset bundle"):
            insert_future.result(timeout=5)

    assert published["status"] == "published"
    assert [event["sequence"] for event in published["lifecycleEvents"]] == [1, 2]
    with scoped_connect() as conn:
        assert conn.execute(
            sql.SQL("SELECT count(*) AS count FROM {}").format(
                sql.Identifier(table)
            )
        ).fetchone()["count"] == count_before


@pytest.mark.parametrize(
    "table",
    [
        "asset_bundle",
        "asset_bundle_version",
        "asset_bundle_dependency",
        "asset_bundle_artifact",
        "asset_bundle_evidence",
    ],
)
def test_canonical_registry_tables_cannot_be_truncated(
    registry_scope,
    table: str,
) -> None:
    _store, scoped_connect = registry_scope
    with scoped_connect() as conn:
        _assert_check_violation(conn, f"TRUNCATE {table} CASCADE")
