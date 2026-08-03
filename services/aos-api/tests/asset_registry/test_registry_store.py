"""PostgreSQL evidence tests for the canonical Registry store."""

from __future__ import annotations

import importlib.util
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import errors, sql
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
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
INVARIANTS_MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_invariants.py"
EVIDENCE_MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py"
INSTALLATION_MIGRATION_PATH = (
    API_ROOT / "alembic/versions/228asset1_composition_installation.py"
)


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
        (INVARIANTS_MIGRATION_PATH, "registry_store_invariants_migration"),
        (EVIDENCE_MIGRATION_PATH, "registry_store_evidence_migration"),
    ):
        module = _load_migration(path, name)
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value = []
        with (
            patch.object(module.op, "execute", statements.append),
            patch.object(module.op, "get_bind", return_value=connection),
        ):
            module.upgrade()
    return statements


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


def _loaded_bundle_with_fixed_evidence_time(
    *,
    bundle_id: str,
    microsecond: int,
) -> LoadedBundle:
    loaded = _loaded_bundle(bundle_id=bundle_id)
    payload = loaded.model_dump(mode="python", by_alias=True)
    observed_at = datetime(2026, 8, 3, 12, 34, 56, microsecond, tzinfo=UTC)
    payload["evidence"][0].update(
        {
            "status": "revoked",
            "observedAt": observed_at,
            "expiresAt": observed_at + timedelta(hours=1),
            "revokedAt": observed_at + timedelta(minutes=30),
            "metadata": {
                "validator": "registry-test",
                "microsecond": microsecond,
            },
        }
    )
    return LoadedBundle.model_validate(payload)


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


def test_security_migrations_form_the_single_head_chain() -> None:
    security = _load_migration(
        SECURITY_MIGRATION_PATH,
        "registry_security_revision_contract",
    )
    invariants = _load_migration(
        INVARIANTS_MIGRATION_PATH,
        "registry_invariants_revision_contract",
    )
    evidence = _load_migration(
        EVIDENCE_MIGRATION_PATH,
        "registry_evidence_revision_contract",
    )
    installation = _load_migration(
        INSTALLATION_MIGRATION_PATH,
        "registry_installation_revision_contract",
    )
    script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))

    assert security.revision == "228assetsecurity"
    assert security.down_revision == "a93c7e1b4f20"
    assert invariants.revision == "228assetinvariants"
    assert invariants.down_revision == "228assetsecurity"
    assert evidence.revision == "228assetevidence"
    assert evidence.down_revision == "228assetinvariants"
    assert installation.revision == "228assetinstall"
    assert installation.down_revision == "228assetevidence"
    assert script.get_heads() == ["228assetintegration"]


def test_invariants_upgrade_is_reachable_from_already_applied_security_revision() -> (
    None
):
    old_upgrade = [
        *_migration_statements(
            MIGRATION_PATH,
            "registry_incremental_base_upgrade",
            "upgrade",
        ),
        *_migration_statements(
            SECURITY_MIGRATION_PATH,
            "registry_incremental_security_upgrade",
            "upgrade",
        ),
    ]
    with _isolated_schema(old_upgrade) as scoped_connect, scoped_connect() as conn:
        assert (
            conn.execute(
                "SELECT to_regprocedure("
                "'lock_asset_registry_projection_statement()') AS function"
            ).fetchone()["function"]
            is None
        )
        for statement in _migration_statements(
            INVARIANTS_MIGRATION_PATH,
            "registry_incremental_invariants_upgrade",
            "upgrade",
        ):
            conn.execute(statement)
        conn.commit()
        triggers = {
            row["tgname"]
            for row in conn.execute(
                """
                    SELECT tgname
                      FROM pg_trigger
                     WHERE NOT tgisinternal
                       AND tgrelid IN (
                         'asset_bundle_version'::regclass,
                         'asset_bundle_evidence'::regclass
                       )
                    """
            ).fetchall()
        }
        assert "trg_asset_bundle_status_event_required" in triggers
        assert "trg_00_asset_bundle_evidence_statement_lock" in triggers
        assert "trg_00_asset_bundle_evidence_parent_lock" in triggers


def test_evidence_upgrade_preserves_old_events_as_explicit_unknown_snapshots() -> None:
    old_upgrade = [
        *_migration_statements(
            MIGRATION_PATH,
            "registry_evidence_incremental_base",
            "upgrade",
        ),
        *_migration_statements(
            SECURITY_MIGRATION_PATH,
            "registry_evidence_incremental_security",
            "upgrade",
        ),
        *_migration_statements(
            INVARIANTS_MIGRATION_PATH,
            "registry_evidence_incremental_invariants",
            "upgrade",
        ),
    ]
    with _isolated_schema(old_upgrade) as scoped_connect:
        store = PostgresRegistryStore(scoped_connect)
        _create_bundle(store, bundle_id="solution.incremental-evidence")
        loaded = _loaded_bundle(bundle_id="solution.incremental-evidence")
        with scoped_connect() as conn:
            bundle_pk = conn.execute("SELECT bundle_pk FROM asset_bundle").fetchone()[
                "bundle_pk"
            ]
            version_pk = uuid.uuid4()
            conn.execute(
                """
                INSERT INTO asset_bundle_version (
                  version_pk, bundle_pk, version, manifest_json,
                  content_hash, signature, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, 'publisher:test')
                """,
                (
                    version_pk,
                    bundle_pk,
                    loaded.manifest.metadata.version,
                    Jsonb(
                        loaded.manifest.model_dump(
                            mode="json", by_alias=True, exclude_none=False
                        )
                    ),
                    loaded.content_hash,
                    Jsonb(
                        loaded.signature.model_dump(
                            mode="json", by_alias=True, exclude_none=False
                        )
                    ),
                ),
            )
            evidence = loaded.evidence[0]
            conn.execute(
                """
                INSERT INTO asset_bundle_evidence (
                  version_pk, evidence_type, artifact_ref, artifact_hash,
                  status, observed_at, expires_at, revoked_at, metadata,
                  updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                          'publisher:test')
                """,
                (
                    version_pk,
                    evidence.type.value,
                    evidence.artifact_ref,
                    evidence.artifact_hash,
                    evidence.status.value,
                    evidence.observed_at,
                    evidence.expires_at,
                    evidence.revoked_at,
                    Jsonb(evidence.metadata),
                ),
            )
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
                          'validator:old-binary', 'pre-snapshot event', %s)
                """,
                (uuid.uuid4(), version_pk, "sha256:" + "e" * 64),
            )
            conn.commit()
            for statement in _migration_statements(
                EVIDENCE_MIGRATION_PATH,
                "registry_evidence_incremental_upgrade",
                "upgrade",
            ):
                conn.execute(statement)
            conn.commit()
            row = conn.execute(
                "SELECT evidence_snapshot FROM asset_bundle_version_event"
            ).fetchone()
            assert row["evidence_snapshot"] is None
            savepoint = sql.Identifier("legacy_evidence_downgrade")
            conn.execute(sql.SQL("SAVEPOINT {}").format(savepoint))
            for statement in _migration_statements(
                EVIDENCE_MIGRATION_PATH,
                "registry_evidence_legacy_only_downgrade",
                "downgrade",
            ):
                conn.execute(statement)
            assert (
                conn.execute(
                    """
                    SELECT 1
                      FROM information_schema.columns
                     WHERE table_schema = current_schema()
                       AND table_name = 'asset_bundle_version_event'
                       AND column_name = 'evidence_snapshot'
                    """
                ).fetchone()
                is None
            )
            conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(savepoint))
            conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(savepoint))

        transitioned = store.transition_version(
            "solution.incremental-evidence",
            "1.0.0",
            {"validated"},
            "rejected",
            "reviewer:new-binary",
        )
        assert transitioned["lifecycleEvents"][0]["evidenceSnapshot"] is None
        assert transitioned["lifecycleEvents"][1]["evidenceSnapshot"]
        assert (
            canonical_sha256(transitioned["lifecycleEvents"][1]["evidenceSnapshot"])
            == transitioned["lifecycleEvents"][1]["evidenceRevision"]
        )


def test_evidence_migration_normalizes_mutable_signature_envelope_hash() -> None:
    module = _load_migration(
        EVIDENCE_MIGRATION_PATH,
        "registry_signature_hash_normalization",
    )
    signature = {
        "algorithm": "Ed25519",
        "keyId": "release-1",
        "signature": "base64-signature",
        "signedAt": "2026-08-03T12:00:00+00:00",
    }
    select_result = MagicMock()
    select_result.mappings.return_value = [
        {
            "version_pk": uuid.uuid4(),
            "signature": signature,
            "artifact_hash": "sha256:" + "f" * 64,
        }
    ]
    connection = MagicMock()
    connection.execute.side_effect = [select_result, MagicMock()]

    with patch.object(module.op, "get_bind", return_value=connection):
        module._normalize_mutable_signature_evidence()

    params = connection.execute.call_args_list[1].args[1]
    assert params["artifact_hash"] == canonical_sha256(signature)
    assert params["hash_profile"] == "canonical-envelope-v1"


def test_database_canonical_evidence_hash_matches_python(registry_scope) -> None:
    _, scoped_connect = registry_scope
    samples = [
        {},
        [],
        {
            "中文": "栖月汇",
            "ascii": "line one\nline two",
            "nested": {
                "false": False,
                "null": None,
                "numbers": [0, -7, 1.0, 0.000001, 1e20],
            },
            "ordered": [{"z": 1, "a": 2}, "尾部"],
        },
    ]

    with scoped_connect() as conn:
        for sample in samples:
            row = conn.execute(
                """
                SELECT %s::JSONB AS roundtripped,
                       canonical_asset_registry_jsonb(%s::JSONB) AS canonical,
                       'sha256:' || encode(
                         public.digest(
                           convert_to(
                             canonical_asset_registry_jsonb(%s::JSONB),
                             'UTF8'
                           ),
                           'sha256'
                         ),
                         'hex'
                       ) AS revision
                """,
                (Jsonb(sample), Jsonb(sample), Jsonb(sample)),
            ).fetchone()
            roundtripped = row["roundtripped"]
            assert row["canonical"].encode("utf-8") == canonical_json(roundtripped)
            assert row["revision"] == canonical_sha256(roundtripped)


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
                    row["evidence_revision"] == "sha256:" + "0" * 64 for row in rows
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
                sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint))
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
    assert [(event["fromStatus"], event["toStatus"]) for event in events] == [
        ("draft", "validated"),
        ("validated", "published"),
    ]
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
    assert (
        restarted.get_version("solution.audit-durable", "1.0.0", "aos")[
            "lifecycleEvents"
        ]
        == events
    )


@pytest.mark.parametrize(
    ("microsecond", "observed_at", "expires_at", "revoked_at"),
    [
        (
            123450,
            "2026-08-03T12:34:56.12345+00:00",
            "2026-08-03T13:34:56.12345+00:00",
            "2026-08-03T13:04:56.12345+00:00",
        ),
        (
            123456,
            "2026-08-03T12:34:56.123456+00:00",
            "2026-08-03T13:34:56.123456+00:00",
            "2026-08-03T13:04:56.123456+00:00",
        ),
        (
            0,
            "2026-08-03T12:34:56+00:00",
            "2026-08-03T13:34:56+00:00",
            "2026-08-03T13:04:56+00:00",
        ),
    ],
)
def test_evidence_timestamps_match_postgresql_json_snapshot_and_restart(
    registry_scope,
    microsecond: int,
    observed_at: str,
    expires_at: str,
    revoked_at: str,
) -> None:
    store, scoped_connect = registry_scope
    bundle_id = f"solution.evidence-time-{microsecond}"
    loaded = _loaded_bundle_with_fixed_evidence_time(
        bundle_id=bundle_id,
        microsecond=microsecond,
    )
    _create_bundle(store, bundle_id=bundle_id)
    created = store.create_version(loaded, "publisher:test")

    transitioned = store.transition_version(
        bundle_id,
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
        "evidence timestamp rendering verified",
    )

    event = transitioned["lifecycleEvents"][0]
    snapshot = event["evidenceSnapshot"]
    assert created["evidence"] == transitioned["evidence"] == snapshot
    assert canonical_sha256(created["evidence"]) == event["evidenceRevision"]
    assert transitioned["evidence"][0] == {
        "type": "manifest_validation",
        "artifactRef": f"bundle://fixtures/aos/{bundle_id}/evidence.json",
        "artifactHash": "sha256:" + "b" * 64,
        "status": "revoked",
        "observedAt": observed_at,
        "expiresAt": expires_at,
        "revokedAt": revoked_at,
        "metadata": {
            "validator": "registry-test",
            "microsecond": microsecond,
        },
    }

    with scoped_connect() as conn:
        persisted = conn.execute(
            """
            SELECT evidence_snapshot
              FROM asset_bundle_version_event
             WHERE version_pk = (
                       SELECT version_pk
                         FROM asset_bundle_version
                        WHERE bundle_pk = (
                                  SELECT bundle_pk
                                    FROM asset_bundle
                                   WHERE publisher = 'aos' AND bundle_id = %s
                              )
                          AND version = '1.0.0'
                   )
               AND sequence = 1
            """,
            (bundle_id,),
        ).fetchone()
    assert persisted is not None
    assert persisted["evidence_snapshot"] == snapshot

    restarted = PostgresRegistryStore(scoped_connect)
    assert restarted.get_version(bundle_id, "1.0.0", "aos") == transitioned


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
        assert (
            conn.execute(
                "SELECT to_regclass('asset_bundle_version_event') AS relation"
            ).fetchone()["relation"]
            == "asset_bundle_version_event"
        )

    with (
        _isolated_schema(_upgrade_statements()) as empty_scoped_connect,
        empty_scoped_connect() as conn,
    ):
        for statement in _migration_statements(
            EVIDENCE_MIGRATION_PATH,
            "registry_evidence_downgrade_empty",
            "downgrade",
        ):
            conn.execute(statement)
        assert (
            conn.execute(
                "SELECT to_regprocedure("
                "'canonical_asset_registry_jsonb(jsonb)') AS function"
            ).fetchone()["function"]
            is None
        )
        assert (
            conn.execute(
                "SELECT extname FROM pg_extension WHERE extname = 'pgcrypto'"
            ).fetchone()["extname"]
            == "pgcrypto"
        )
        for statement in _migration_statements(
            INVARIANTS_MIGRATION_PATH,
            "registry_invariants_downgrade_empty",
            "downgrade",
        ):
            conn.execute(statement)
        for statement in _migration_statements(
            SECURITY_MIGRATION_PATH,
            "registry_security_downgrade_empty",
            "downgrade",
        ):
            conn.execute(statement)
        conn.commit()
        assert (
            conn.execute(
                "SELECT to_regclass('asset_bundle_version_event') AS relation"
            ).fetchone()["relation"]
            is None
        )
        assert (
            conn.execute(
                "SELECT to_regclass('asset_bundle_version') AS relation"
            ).fetchone()["relation"]
            == "asset_bundle_version"
        )


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
        assert (
            conn.execute(
                "SELECT count(*) AS count FROM asset_bundle_version_event"
            ).fetchone()["count"]
            == 0
        )

        conn.execute("SAVEPOINT forged_evidence_revision")
        conn.execute(
            "UPDATE asset_bundle_version SET status = 'validated' "
            "WHERE version_pk = %s",
            (version_pk,),
        )
        snapshot = store._load_evidence_snapshot(conn, version_pk)
        with pytest.raises(errors.CheckViolation, match="revision is invalid"):
            conn.execute(
                """
                INSERT INTO asset_bundle_version_event (
                  event_pk, version_pk, sequence, from_status, to_status,
                  actor, reason, evidence_revision, evidence_snapshot
                ) VALUES (%s, %s, 1, 'draft', 'validated',
                          'validator:sql', 'forged revision', %s, %s)
                """,
                (
                    uuid.uuid4(),
                    version_pk,
                    "sha256:" + "f" * 64,
                    Jsonb(snapshot),
                ),
            )
        conn.execute("ROLLBACK TO SAVEPOINT forged_evidence_revision")
        conn.execute("RELEASE SAVEPOINT forged_evidence_revision")

        conn.execute(
            "UPDATE asset_bundle_version SET status = 'validated' "
            "WHERE version_pk = %s",
            (version_pk,),
        )
        snapshot = store._load_evidence_snapshot(conn, version_pk)
        conn.execute(
            """
            INSERT INTO asset_bundle_version_event (
              event_pk, version_pk, sequence, from_status, to_status,
              actor, reason, evidence_revision, evidence_snapshot
            ) VALUES (%s, %s, 1, 'draft', 'validated',
                      'validator:sql', 'atomic transition', %s, %s)
            """,
            (
                uuid.uuid4(),
                version_pk,
                canonical_sha256(snapshot),
                Jsonb(snapshot),
            ),
        )
        conn.commit()

    restarted = PostgresRegistryStore(scoped_connect)
    record = restarted.get_version("solution.deferred-audit", "1.0.0", "aos")
    assert record["status"] == "validated"
    assert [
        (event["sequence"], event["fromStatus"], event["toStatus"])
        for event in record["lifecycleEvents"]
    ] == [(1, "draft", "validated")]


def test_transition_precondition_cannot_mutate_persisted_evidence_snapshot(
    registry_scope,
) -> None:
    store, _ = registry_scope
    _create_bundle(store, bundle_id="solution.precondition-isolated")
    created = store.create_version(
        _loaded_bundle(bundle_id="solution.precondition-isolated"),
        "publisher:test",
    )

    def mutate_callback(record: dict) -> None:
        record["evidence"][0]["metadata"] = {"attacker": True}

    transitioned = store.transition_version(
        "solution.precondition-isolated",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
        precondition=mutate_callback,
    )

    snapshot = transitioned["lifecycleEvents"][0]["evidenceSnapshot"]
    assert snapshot == created["evidence"]
    assert snapshot[0]["metadata"] == {"validator": "registry-test"}
    assert (
        canonical_sha256(snapshot)
        == transitioned["lifecycleEvents"][0]["evidenceRevision"]
    )


def test_evidence_snapshot_downgrade_blocks_every_new_event(registry_scope) -> None:
    store, scoped_connect = registry_scope
    _create_bundle(store, bundle_id="solution.evidence-downgrade")
    store.create_version(
        _loaded_bundle(bundle_id="solution.evidence-downgrade"),
        "publisher:test",
    )
    store.transition_version(
        "solution.evidence-downgrade",
        "1.0.0",
        {"draft"},
        "validated",
        "validator:test",
    )

    with scoped_connect() as conn:
        with pytest.raises(errors.CheckViolation, match="snapshots exist"):
            for statement in _migration_statements(
                EVIDENCE_MIGRATION_PATH,
                "registry_evidence_snapshot_downgrade_blocked",
                "downgrade",
            ):
                conn.execute(statement)
        conn.rollback()
        assert (
            conn.execute(
                """
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                   AND table_name = 'asset_bundle_version_event'
                   AND column_name = 'evidence_snapshot'
                """
            ).fetchone()
            is not None
        )


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
            sql.SQL("SELECT count(*) AS count FROM {}").format(sql.Identifier(table))
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
        assert (
            conn.execute(
                sql.SQL("SELECT count(*) AS count FROM {}").format(
                    sql.Identifier(table)
                )
            ).fetchone()["count"]
            == count_before
        )


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


@pytest.mark.parametrize(
    ("updated_status", "expected_outcome"),
    [("valid", "published"), ("invalid", "rejected")],
)
def test_evidence_update_and_publish_follow_advisory_lock_order(
    registry_scope,
    updated_status: str,
    expected_outcome: str,
) -> None:
    store, scoped_connect = registry_scope
    bundle_id = f"solution.evidence-race-{updated_status}"
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

    evidence_updated = Event()
    allow_evidence_commit = Event()
    publish_connected = Event()
    gate_observed_update = Event()
    publish_pid: dict[str, int] = {}

    def update_evidence() -> str:
        with scoped_connect() as conn:
            conn.execute(
                """
                UPDATE asset_bundle_evidence
                   SET status = %s,
                       metadata = '{"revision":"concurrent-update"}'::JSONB,
                       updated_at = clock_timestamp(),
                       updated_by = 'evidence:worker',
                       status_reason = 'concurrent evidence refresh'
                 WHERE version_pk = %s
                """,
                (updated_status, version_pk),
            )
            evidence_updated.set()
            assert allow_evidence_commit.wait(timeout=5)
            conn.commit()
        return updated_status

    @contextmanager
    def publish_connect():
        with scoped_connect() as conn:
            publish_pid["value"] = conn.execute(
                "SELECT pg_backend_pid() AS pid"
            ).fetchone()["pid"]
            publish_connected.set()
            yield conn

    def evidence_gate(record: dict) -> None:
        evidence = record["evidence"]
        assert len(evidence) == 1
        assert evidence[0]["metadata"] == {"revision": "concurrent-update"}
        gate_observed_update.set()
        if evidence[0]["status"] != "valid":
            raise VersionInvalidError("updated evidence failed the publish gate")

    def publish() -> tuple[str, dict | None, int, str | None]:
        publish_store = PostgresRegistryStore(publish_connect)
        try:
            record = publish_store.transition_version(
                bundle_id,
                "1.0.0",
                {"validated"},
                "published",
                "publisher:test",
                precondition=evidence_gate,
            )
        except VersionInvalidError as exc:
            return "rejected", None, exc.http_status, exc.code.value
        return "published", record, 200, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        update_future = executor.submit(update_evidence)
        assert evidence_updated.wait(timeout=5)
        publish_future = executor.submit(publish)
        try:
            assert publish_connected.wait(timeout=5)
            deadline = time.monotonic() + 5
            while True:
                with connect() as conn:
                    waiting = conn.execute(
                        """
                        SELECT EXISTS (
                          SELECT 1
                            FROM pg_locks
                           WHERE pid = %s
                             AND locktype = 'advisory'
                             AND NOT granted
                        ) AS waiting
                        """,
                        (publish_pid["value"],),
                    ).fetchone()["waiting"]
                if waiting:
                    break
                if time.monotonic() >= deadline:
                    pytest.fail("publish did not wait for the evidence writer lock")
                time.sleep(0.01)
        finally:
            allow_evidence_commit.set()

        assert update_future.result(timeout=5) == updated_status
        outcome, published, http_status, error_code = publish_future.result(timeout=5)

    assert gate_observed_update.is_set()
    assert outcome == expected_outcome
    assert http_status != 500
    restarted = PostgresRegistryStore(scoped_connect)
    record = restarted.get_version(bundle_id, "1.0.0", "aos")
    assert record["evidence"][0]["status"] == updated_status
    assert record["evidence"][0]["metadata"] == {"revision": "concurrent-update"}
    if expected_outcome == "published":
        assert published is not None
        assert (http_status, error_code) == (200, None)
        assert record["status"] == "published"
        assert [event["sequence"] for event in record["lifecycleEvents"]] == [1, 2]
    else:
        assert published is None
        assert (http_status, error_code) == (400, "VERSION_INVALID")
        assert record["status"] == "validated"
        assert [event["sequence"] for event in record["lifecycleEvents"]] == [1]
