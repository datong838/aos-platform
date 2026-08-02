"""PostgreSQL evidence tests for the canonical Registry store."""

from __future__ import annotations

import importlib.util
import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
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

    yield PostgresRegistryStore(scoped_connect), scoped_connect

    with connect() as conn:
        conn.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
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
