"""M1 end-to-end Registry evidence through loader, service, store, and PostgreSQL."""
from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
import yaml
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.errors import (
    DutySeparationRequiredError,
    RevisionConflictError,
    SignatureInvalidError,
)
from aos_api.asset_registry.manifest_loader import (
    BUNDLE_EVALS_RELATIVE_PATH,
    SBOM_RELATIVE_PATH,
    SIGNATURE_FILENAME,
    ManifestLoader,
)
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.signature import TrustRoot
from aos_api.db import connect
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import errors, sql

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_registry.py"
SECURITY_MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_security.py"
INVARIANTS_MIGRATION_PATH = API_ROOT / "alembic/versions/228asset0_invariants.py"
CREATE_ROLES = {"developer"}
PUBLISH_ROLES = {"asset-publisher"}


class RuntimeTrustRoots:
    def __init__(self) -> None:
        self._roots: dict[tuple[str, str], TrustRoot] = {}

    def add(self, root: TrustRoot) -> None:
        self._roots[(root.publisher, root.key_id)] = root

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        return self._roots.get((publisher, key_id))


def _load_migration(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements() -> list[str]:
    statements: list[str] = []
    for path, name in (
        (MIGRATION_PATH, "registry_e2e_migration"),
        (SECURITY_MIGRATION_PATH, "registry_e2e_security_migration"),
        (INVARIANTS_MIGRATION_PATH, "registry_e2e_invariants_migration"),
    ):
        module = _load_migration(path, name)
        with patch.object(module.op, "execute", statements.append):
            module.upgrade()
    return statements


@pytest.fixture()
def registry_runtime():
    schema = f"asset_registry_e2e_{uuid.uuid4().hex}"
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
        with connect() as cleanup:
            cleanup.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            cleanup.commit()
        raise

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield conn

    with tempfile.TemporaryDirectory(prefix="aos-registry-e2e-") as temp_dir:
        try:
            yield Path(temp_dir), scoped_connect
        finally:
            if created:
                with connect() as cleanup:
                    cleanup.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(schema)
                        )
                    )
                    cleanup.commit()


def _manifest(
    *,
    publisher: str,
    bundle_id: str,
    version: str = "1.0.0",
    display_name: str = "Generic Utilities",
) -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "PluginPack",
        "metadata": {
            "id": bundle_id,
            "version": version,
            "displayName": display_name,
            "publisher": publisher,
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "exports": {},
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {
                "plan": None,
                "downgradePolicy": "retain-canonical",
            },
            "preflight": None,
            "regression": None,
            "rollback": None,
        },
    }


def _write_bundle(
    root: Path,
    *,
    directory: str,
    publisher: str,
    bundle_id: str,
    display_name: str = "Generic Utilities",
) -> Path:
    bundle = root / directory
    (bundle / "evidence").mkdir(parents=True)
    (bundle / "bundle.yaml").write_text(
        yaml.safe_dump(
            _manifest(
                publisher=publisher,
                bundle_id=bundle_id,
                display_name=display_name,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (bundle / SBOM_RELATIVE_PATH).write_text(
        json.dumps({"format": "CycloneDX", "components": []}),
        encoding="utf-8",
    )
    (bundle / BUNDLE_EVALS_RELATIVE_PATH).write_text(
        json.dumps({"status": "passed", "failed": 0}),
        encoding="utf-8",
    )
    return bundle


def _signature_payload(loaded) -> bytes:
    return canonical_json(
        {
            "manifest": loaded.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "artifacts": [
                {
                    "relativePath": artifact.relative_path,
                    "digest": artifact.digest,
                    "size": artifact.size,
                    "mediaType": artifact.media_type,
                }
                for artifact in loaded.artifacts
            ],
        }
    )


def _sign_bundle(
    *,
    loader: ManifestLoader,
    source_ref: str,
    bundle: Path,
    publisher: str,
    trust_roots: RuntimeTrustRoots,
    invalid: bool = False,
) -> TrustRoot:
    unsigned = loader.load(source_ref)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    now = datetime.now(UTC)
    key_id = f"runtime-{uuid.uuid4().hex}"
    payload = _signature_payload(unsigned)
    if invalid:
        payload += b"tampered"
    envelope = {
        "algorithm": "Ed25519",
        "keyId": key_id,
        "signature": base64.b64encode(private_key.sign(payload)).decode("ascii"),
        "signedAt": now.isoformat(),
    }
    (bundle / SIGNATURE_FILENAME).write_text(
        json.dumps(envelope), encoding="utf-8"
    )
    trust_root = TrustRoot(
        publisher=publisher,
        key_id=key_id,
        public_key=public_key,
        revision="sha256:" + "a" * 64,
        not_before=now - timedelta(minutes=1),
        not_after=now + timedelta(minutes=10),
    )
    trust_roots.add(trust_root)
    return trust_root


def _create_bundle_and_version(
    service: RegistryService,
    *,
    publisher: str,
    bundle_id: str,
    source_ref: str,
    display_name: str = "Generic Utilities",
) -> dict:
    service.create_bundle(
        publisher=publisher,
        bundle_id=bundle_id,
        kind="PluginPack",
        display_name=display_name,
        actor=f"author:{publisher}",
        roles=CREATE_ROLES,
        publisher_scopes={publisher},
    )
    return service.create_version(
        publisher=publisher,
        bundle_id=bundle_id,
        source_ref=source_ref,
        actor=f"author:{publisher}",
        roles=CREATE_ROLES,
        publisher_scopes={publisher},
    )


def _assert_check_violation(conn, statement: str, params: tuple) -> None:
    name = f"expected_failure_{uuid.uuid4().hex}"
    conn.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(name)))
    with pytest.raises(errors.CheckViolation):
        conn.execute(statement, params)
    conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(name)))
    conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(name)))


def test_signed_bundle_publishes_and_survives_store_restart(registry_runtime) -> None:
    root, scoped_connect = registry_runtime
    trust_roots = RuntimeTrustRoots()
    bundle = _write_bundle(
        root,
        directory="generic-good",
        publisher="aos",
        bundle_id="plugin.generic",
    )
    unsigned_loader = ManifestLoader({"fixtures": root})
    source_ref = "bundle://fixtures/generic-good"
    trust_root = _sign_bundle(
        loader=unsigned_loader,
        source_ref=source_ref,
        bundle=bundle,
        publisher="aos",
        trust_roots=trust_roots,
    )
    loader = ManifestLoader({"fixtures": root}, trust_roots=trust_roots)
    service = RegistryService(
        store=PostgresRegistryStore(scoped_connect), loader=loader
    )

    draft = _create_bundle_and_version(
        service,
        publisher="aos",
        bundle_id="plugin.generic",
        source_ref=source_ref,
    )
    assert draft["status"] == "draft"
    assert {item["type"] for item in draft["evidence"]} >= {
        "manifest_validation",
        "content_hash",
        "signature_verification",
        "sbom",
        "bundle_evals",
    }
    assert all(item["status"] == "valid" for item in draft["evidence"])
    signature_evidence = next(
        item for item in draft["evidence"] if item["type"] == "signature_verification"
    )
    assert signature_evidence["metadata"]["trustRootRevision"] == (
        trust_root.revision
    )
    assert signature_evidence["expiresAt"] == trust_root.not_after.isoformat()
    assert draft["lifecycleEvents"] == []

    validated = service.validate(
        bundle_id="plugin.generic",
        version="1.0.0",
        publisher="aos",
        actor="validator:aos",
        roles=CREATE_ROLES,
        publisher_scopes={"aos"},
    )
    assert validated["status"] == "validated"
    assert [event["sequence"] for event in validated["lifecycleEvents"]] == [1]
    assert validated["lifecycleEvents"][0]["actor"] == "validator:aos"

    for actor in ("author:aos", "validator:aos"):
        with pytest.raises(DutySeparationRequiredError):
            service.publish(
                bundle_id="plugin.generic",
                version="1.0.0",
                publisher="aos",
                actor=actor,
                roles=PUBLISH_ROLES,
                publisher_scopes={"aos"},
            )
    published = service.publish(
        bundle_id="plugin.generic",
        version="1.0.0",
        publisher="aos",
        actor="publisher:aos",
        roles=PUBLISH_ROLES,
        publisher_scopes={"aos"},
    )
    assert published["status"] == "published"
    assert [event["sequence"] for event in published["lifecycleEvents"]] == [1, 2]
    assert [event["actor"] for event in published["lifecycleEvents"]] == [
        "validator:aos",
        "publisher:aos",
    ]
    assert [
        (event["fromStatus"], event["toStatus"])
        for event in published["lifecycleEvents"]
    ] == [("draft", "validated"), ("validated", "published")]
    assert all(
        event["evidenceRevision"].startswith("sha256:")
        for event in published["lifecycleEvents"]
    )

    restarted_service = RegistryService(
        store=PostgresRegistryStore(scoped_connect), loader=loader
    )
    assert (
        restarted_service.get_version(
            bundle_id="plugin.generic", version="1.0.0", publisher="aos"
        )
        == published
    )

    with scoped_connect() as conn:
        _assert_check_violation(
            conn,
            """
            UPDATE asset_bundle_version
               SET content_hash = %s
             WHERE version_pk = (
               SELECT v.version_pk
                 FROM asset_bundle_version v
                 JOIN asset_bundle b USING (bundle_pk)
                WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
             )
            """,
            ("sha256:" + "d" * 64, "aos", "plugin.generic", "1.0.0"),
        )
        _assert_check_violation(
            conn,
            """
            DELETE FROM asset_bundle_version
             WHERE version_pk = (
               SELECT v.version_pk
                 FROM asset_bundle_version v
                 JOIN asset_bundle b USING (bundle_pk)
                WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
             )
            """,
            ("aos", "plugin.generic", "1.0.0"),
        )
        conn.rollback()


def test_invalid_signature_and_dual_publishers_fail_closed(registry_runtime) -> None:
    root, scoped_connect = registry_runtime
    trust_roots = RuntimeTrustRoots()
    unsigned_loader = ManifestLoader({"fixtures": root})

    bad_bundle = _write_bundle(
        root,
        directory="generic-bad-signature",
        publisher="aos",
        bundle_id="plugin.bad-signature",
    )
    bad_ref = "bundle://fixtures/generic-bad-signature"
    _sign_bundle(
        loader=unsigned_loader,
        source_ref=bad_ref,
        bundle=bad_bundle,
        publisher="aos",
        trust_roots=trust_roots,
        invalid=True,
    )
    shared_roots: dict[str, TrustRoot] = {}
    for publisher, directory in (("aos", "shared-aos"), ("partner", "shared-partner")):
        bundle = _write_bundle(
            root,
            directory=directory,
            publisher=publisher,
            bundle_id="plugin.shared",
        )
        shared_roots[publisher] = _sign_bundle(
            loader=unsigned_loader,
            source_ref=f"bundle://fixtures/{directory}",
            bundle=bundle,
            publisher=publisher,
            trust_roots=trust_roots,
        )

    loader = ManifestLoader({"fixtures": root}, trust_roots=trust_roots)
    service = RegistryService(
        store=PostgresRegistryStore(scoped_connect), loader=loader
    )
    _create_bundle_and_version(
        service,
        publisher="aos",
        bundle_id="plugin.bad-signature",
        source_ref=bad_ref,
    )
    with pytest.raises(SignatureInvalidError):
        service.validate(
            bundle_id="plugin.bad-signature",
            version="1.0.0",
            publisher="aos",
            actor="validator:aos",
            roles=CREATE_ROLES,
            publisher_scopes={"aos"},
        )
    assert service.get_version(
        bundle_id="plugin.bad-signature", version="1.0.0", publisher="aos"
    )["status"] == "draft"

    for publisher, directory in (("aos", "shared-aos"), ("partner", "shared-partner")):
        _create_bundle_and_version(
            service,
            publisher=publisher,
            bundle_id="plugin.shared",
            source_ref=f"bundle://fixtures/{directory}",
        )
    with pytest.raises(RevisionConflictError, match="ambiguous"):
        service.get_version(bundle_id="plugin.shared", version="1.0.0")

    validated = service.validate(
        bundle_id="plugin.shared",
        version="1.0.0",
        publisher="partner",
        actor="validator:partner",
        roles=CREATE_ROLES,
        publisher_scopes={"partner"},
    )
    assert validated["publisher"] == "partner"
    assert validated["status"] == "validated"
    assert service.get_version(
        bundle_id="plugin.shared", version="1.0.0", publisher="aos"
    )["status"] == "draft"

    trust_roots.add(
        replace(
            shared_roots["partner"],
            revision="sha256:" + "b" * 64,
        )
    )
    with pytest.raises(SignatureInvalidError, match="stale"):
        service.publish(
            bundle_id="plugin.shared",
            version="1.0.0",
            publisher="partner",
            actor="publisher:partner",
            roles=PUBLISH_ROLES,
            publisher_scopes={"partner"},
        )
    assert service.get_version(
        bundle_id="plugin.shared", version="1.0.0", publisher="partner"
    )["status"] == "validated"


def test_service_projection_failure_rolls_back_every_version_table(
    registry_runtime,
) -> None:
    root, scoped_connect = registry_runtime
    trust_roots = RuntimeTrustRoots()
    bundle = _write_bundle(
        root,
        directory="generic-rollback",
        publisher="aos",
        bundle_id="plugin.rollback",
    )
    source_ref = "bundle://fixtures/generic-rollback"
    unsigned_loader = ManifestLoader({"fixtures": root})
    _sign_bundle(
        loader=unsigned_loader,
        source_ref=source_ref,
        bundle=bundle,
        publisher="aos",
        trust_roots=trust_roots,
    )
    loader = ManifestLoader({"fixtures": root}, trust_roots=trust_roots)
    healthy_store = PostgresRegistryStore(scoped_connect)
    healthy_service = RegistryService(store=healthy_store, loader=loader)
    healthy_service.create_bundle(
        publisher="aos",
        bundle_id="plugin.rollback",
        kind="PluginPack",
        display_name="Generic Utilities",
        actor="author:aos",
        roles=CREATE_ROLES,
        publisher_scopes={"aos"},
    )

    class FailOnEvidence:
        def __init__(self, conn) -> None:
            self._conn = conn

        def execute(self, statement, params=None):
            if "INSERT INTO asset_bundle_evidence" in str(statement):
                raise RuntimeError("injected evidence write failure")
            return self._conn.execute(statement, params)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    @contextmanager
    def failing_connect():
        with scoped_connect() as conn:
            yield FailOnEvidence(conn)

    failing_service = RegistryService(
        store=PostgresRegistryStore(failing_connect), loader=loader
    )
    with pytest.raises(RuntimeError, match="injected evidence"):
        failing_service.create_version(
            bundle_id="plugin.rollback",
            source_ref=source_ref,
            publisher="aos",
            actor="author:aos",
            roles=CREATE_ROLES,
            publisher_scopes={"aos"},
        )

    with scoped_connect() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM asset_bundle_version) AS versions,
              (SELECT count(*) FROM asset_bundle_dependency) AS dependencies,
              (SELECT count(*) FROM asset_bundle_artifact) AS artifacts,
              (SELECT count(*) FROM asset_bundle_evidence) AS evidence
            """
        ).fetchone()
    assert dict(row) == {
        "versions": 0,
        "dependencies": 0,
        "artifacts": 0,
        "evidence": 0,
    }
