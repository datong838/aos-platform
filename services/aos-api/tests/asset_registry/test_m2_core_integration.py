"""Independent real-PostgreSQL integration checks for the M2-A1 core."""

from __future__ import annotations

import base64
import importlib.util
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from sqlalchemy import create_engine, text

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    CreateInstallationRequest,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
)
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.contracts import (
    BundleEvidenceType,
    BundleManifest,
    BundleSignature,
    LoadedBundle,
)
from aos_api.asset_registry.errors import AssetRegistryError, AssetRegistryErrorCode
from aos_api.asset_registry.installation_store import (
    CommandResult,
    PostgresInstallationStore,
    command_request_hash,
)
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import (
    REQUIRED_RELEASE_EVIDENCE,
    ReleasePolicy,
)
from aos_api.asset_registry.resolver import resolve
from aos_api.asset_registry.signature import TrustRoot
from aos_api.db import connect, get_dsn

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATHS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
    API_ROOT / "alembic/versions/228asset1_composition_installation.py",
)
NOW = datetime.now(UTC).replace(microsecond=0)


def _load_migration(path: Path, index: int) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"w4_core_migration_{index}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def core_database():
    schema = f"m2_w4_{uuid.uuid4().hex}"
    engine = create_engine(
        get_dsn().replace("postgresql://", "postgresql+psycopg://", 1)
    )
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
            connection.execute(text(f'SET search_path TO "{schema}"'))
            migration_context = MigrationContext.configure(connection)
            with Operations.context(migration_context):
                for index, path in enumerate(MIGRATION_PATHS):
                    _load_migration(path, index).upgrade()
    except Exception as exc:
        if not created:
            pytest.skip(f"PG unavailable: {exc}")
        raise

    @contextmanager
    def scoped_connect():
        with connect() as connection:
            connection.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield connection

    try:
        yield scoped_connect
    finally:
        engine.dispose()
        if created:
            with connect() as connection:
                connection.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
                connection.commit()


class TrustRoots:
    def __init__(self) -> None:
        self.roots: dict[tuple[str, str], TrustRoot] = {}
        self.private_keys: dict[str, Ed25519PrivateKey] = {}
        self.failure: Exception | None = None

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if self.failure is not None:
            raise self.failure
        return self.roots.get((publisher, key_id))

    def signing_material(self, publisher: str) -> tuple[Ed25519PrivateKey, TrustRoot]:
        private_key = self.private_keys.get(publisher)
        if private_key is None:
            private_key = Ed25519PrivateKey.generate()
            self.private_keys[publisher] = private_key
        key_id = f"{publisher}-w4-key"
        root = TrustRoot(
            publisher=publisher,
            key_id=key_id,
            public_key=private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ),
            revision=canonical_sha256({"publisher": publisher, "root": "w4"}),
            not_before=NOW - timedelta(days=1),
            not_after=NOW + timedelta(days=7),
        )
        self.roots[(publisher, key_id)] = root
        return private_key, root


class FixedLoader:
    def __init__(self, loaded: LoadedBundle, trust_roots: TrustRoots) -> None:
        self.loaded = loaded
        self.trust_roots = trust_roots

    def load(self, source_ref: str) -> LoadedBundle:
        if source_ref != self.loaded.source_ref:
            raise AssertionError("unexpected source reference")
        return self.loaded


def _manifest(publisher: str, bundle_id: str, version: str) -> BundleManifest:
    return BundleManifest.model_validate(
        {
            "apiVersion": "aos.dev/v1alpha1",
            "kind": "SolutionPack",
            "metadata": {
                "id": bundle_id,
                "version": version,
                "displayName": f"W4 {bundle_id}",
                "publisher": publisher,
                "license": "internal",
            },
            "spec": {
                "platformApi": ">=1.0.0 <2.0.0",
                "dependencies": [],
                "optionalDependencies": [],
                "conflicts": [],
                "exports": {},
                "capabilities": {"provides": [], "requires": []},
                "permissions": {
                    "roles": ["viewer"],
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
    )


def _signed_bundle(
    trust_roots: TrustRoots,
    *,
    publisher: str,
    bundle_id: str,
    version: str,
) -> LoadedBundle:
    private_key, root = trust_roots.signing_material(publisher)
    manifest = _manifest(publisher, bundle_id, version)
    source_ref = f"bundle://w4/{publisher}/{bundle_id}/{version}"
    descriptor = {
        "manifest": manifest.model_dump(mode="json", by_alias=True, exclude_none=False),
        "artifacts": [],
    }
    content_hash = canonical_sha256(descriptor)
    signature = BundleSignature.model_validate(
        {
            "algorithm": "Ed25519",
            "keyId": root.key_id,
            "signature": base64.b64encode(
                private_key.sign(canonical_json(descriptor))
            ).decode("ascii"),
            "signedAt": NOW,
        }
    )
    signature_hash = canonical_sha256(
        signature.model_dump(mode="json", by_alias=True, exclude_none=False)
    )
    evidence = []
    for evidence_type in REQUIRED_RELEASE_EVIDENCE:
        artifact_hash = canonical_sha256(
            {"bundle": bundle_id, "type": evidence_type.value}
        )
        if evidence_type == BundleEvidenceType.CONTENT_HASH:
            artifact_hash = content_hash
        elif evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION:
            artifact_hash = signature_hash
        evidence.append(
            {
                "type": evidence_type,
                "artifactRef": f"{source_ref}/evidence/{evidence_type.value}.json",
                "artifactHash": artifact_hash,
                "status": "valid",
                "observedAt": NOW - timedelta(minutes=5),
                "expiresAt": (
                    root.not_after
                    if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION
                    else NOW + timedelta(days=8)
                ),
                "revokedAt": None,
                "metadata": (
                    {"trustRootRevision": root.revision}
                    if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION
                    else {}
                ),
            }
        )
    return LoadedBundle.model_validate(
        {
            "sourceRef": source_ref,
            "manifest": manifest,
            "artifacts": [],
            "evidence": evidence,
            "contentHash": content_hash,
            "signature": signature,
            "loadedAt": NOW,
        }
    )


def _publish_bundle(
    store: PostgresRegistryStore,
    trust_roots: TrustRoots,
    *,
    bundle_id: str,
    publisher: str = "aos",
    version: str = "1.0.0",
) -> None:
    loaded = _signed_bundle(
        trust_roots,
        publisher=publisher,
        bundle_id=bundle_id,
        version=version,
    )
    service = RegistryService(
        store=store,
        loader=FixedLoader(loaded, trust_roots),
        clock=lambda: NOW,
        trust_roots=trust_roots,
    )
    service.create_bundle(
        publisher=publisher,
        bundle_id=bundle_id,
        kind="SolutionPack",
        display_name=f"W4 {bundle_id}",
        actor="w4-author",
        roles={"developer"},
        publisher_scopes={publisher},
    )
    service.create_version(
        bundle_id=bundle_id,
        source_ref=loaded.source_ref,
        actor="w4-author",
        roles={"developer"},
        publisher=publisher,
        publisher_scopes={publisher},
    )
    service.validate(
        bundle_id=bundle_id,
        version=version,
        actor="w4-validator",
        roles={"developer"},
        publisher=publisher,
        publisher_scopes={publisher},
    )
    service.publish(
        bundle_id=bundle_id,
        version=version,
        actor="w4-publisher",
        roles={"asset-publisher"},
        publisher=publisher,
        publisher_scopes={publisher},
    )


def _snapshot_reader(scoped_connect, trust_roots: TrustRoots) -> RegistrySnapshotReader:
    return RegistrySnapshotReader(
        connect_factory=scoped_connect,
        release_policy=ReleasePolicy(trust_roots=trust_roots),
    )


def _composition_input() -> tuple[
    CompositionRequest,
    RegistrySnapshot,
    CompositionLockPayload,
]:
    manifest = _manifest("aos", "solution.locked", "1.0.0")
    candidate = RegistrySnapshotCandidate.model_validate(
        {
            "publisher": "aos",
            "id": "solution.locked",
            "version": "1.0.0",
            "kind": "SolutionPack",
            "manifest": manifest,
            "contentHash": canonical_sha256({"content": "locked"}),
            "signatureFingerprint": canonical_sha256({"signature": "locked"}),
            "releaseEvidenceRevision": canonical_sha256({"evidence": "locked"}),
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": ["viewer"],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migration": {
                "planRef": None,
                "downgradePolicy": "retain-canonical",
            },
            "contributions": [],
        }
    )
    snapshot = RegistrySnapshot.build(candidates=[candidate], checked_at=NOW)
    request = CompositionRequest.model_validate(
        {
            "requested": [
                {
                    "publisher": "aos",
                    "id": "solution.locked",
                    "version": "1.0.0",
                }
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": snapshot.snapshot_hash,
            "currentInstallationRef": None,
        }
    )
    return request, snapshot, resolve(request, snapshot, None)


def _persist_lock(scoped_connect, *, org_id: str = "org-a"):
    request, snapshot, payload = _composition_input()
    store = PostgresCompositionStore(scoped_connect)
    lock = store.create_or_get(
        org_id=org_id,
        project_id="project-a",
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="w4-user",
    )
    return store, request, snapshot, payload, lock


def test_snapshot_expiry_does_not_dos_other_candidates(core_database) -> None:
    scoped_connect = core_database
    registry = PostgresRegistryStore(scoped_connect)
    trust_roots = TrustRoots()
    _publish_bundle(registry, trust_roots, bundle_id="solution.expiring")
    _publish_bundle(registry, trust_roots, bundle_id="solution.healthy")

    with scoped_connect() as connection:
        connection.execute(
            """
            UPDATE asset_bundle_evidence AS e
               SET status = 'expired',
                   updated_at = clock_timestamp() + INTERVAL '1 second',
                   updated_by = 'w4-monitor',
                   status_reason = 'expired by W4 adversarial test'
              FROM asset_bundle_version AS v
              JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
             WHERE e.version_pk = v.version_pk
               AND b.bundle_id = 'solution.expiring'
               AND e.evidence_type = 'sbom'
            """
        )
        connection.commit()

    snapshot = _snapshot_reader(scoped_connect, trust_roots).read()

    assert [item.id for item in snapshot.candidates] == ["solution.healthy"]


def test_snapshot_trust_outage_and_manifest_corruption_fail_closed(
    core_database,
) -> None:
    scoped_connect = core_database
    registry = PostgresRegistryStore(scoped_connect)
    trust_roots = TrustRoots()
    _publish_bundle(registry, trust_roots, bundle_id="solution.secure")
    reader = _snapshot_reader(scoped_connect, trust_roots)

    trust_roots.failure = RuntimeError("private provider detail")
    with pytest.raises(AssetRegistryError) as outage:
        reader.read()
    assert outage.value.code == AssetRegistryErrorCode.TRUST_ROOT_UNAVAILABLE
    assert "private provider detail" not in str(outage.value)
    trust_roots.failure = None

    with scoped_connect() as connection:
        connection.execute(
            "ALTER TABLE asset_bundle_version "
            "DISABLE TRIGGER trg_asset_bundle_version_guard"
        )
        connection.execute(
            """
            UPDATE asset_bundle_version
               SET manifest_json = jsonb_set(
                     manifest_json,
                     '{metadata,id}',
                     '"solution.tampered"'::JSONB
                   )
            """
        )
        connection.execute(
            "ALTER TABLE asset_bundle_version "
            "ENABLE TRIGGER trg_asset_bundle_version_guard"
        )
        connection.commit()

    with pytest.raises(AssetRegistryError) as corruption:
        reader.read()
    assert corruption.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


def test_resolver_lock_store_tenants_equivalence_and_installation_primitives(
    core_database,
) -> None:
    scoped_connect = core_database
    store, request, snapshot, payload, lock = _persist_lock(scoped_connect)

    reloaded = store.get_lock(
        org_id="org-a",
        project_id="project-a",
        composition_id=lock.composition_id,
    )
    replay = store.create_or_get(
        org_id="org-a",
        project_id="project-a",
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="w4-user",
    )
    other_tenant = store.create_or_get(
        org_id="org-b",
        project_id="project-a",
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="w4-user",
    )

    assert reloaded == lock
    assert replay.composition_id == lock.composition_id
    assert other_tenant.composition_id != lock.composition_id
    assert lock.lock_hash == canonical_sha256(payload.hash_payload_dump())
    with pytest.raises(AssetRegistryError) as cross_tenant:
        store.get_lock(
            org_id="org-b",
            project_id="project-a",
            composition_id=lock.composition_id,
        )
    assert cross_tenant.value.code == AssetRegistryErrorCode.NOT_FOUND

    different_payload_json = payload.model_dump(
        mode="json", by_alias=True, exclude_none=False
    )
    different_payload_json["resolved"][0]["contentHash"] = canonical_sha256(
        {"forged": "different deterministic output"}
    )
    different_payload = CompositionLockPayload.model_validate(different_payload_json)
    with pytest.raises(AssetRegistryError) as equivalent_conflict:
        store.create_or_get(
            org_id="org-a",
            project_id="project-a",
            request=request,
            snapshot=snapshot,
            payload=different_payload,
            created_by="w4-user",
        )
    assert (
        equivalent_conflict.value.code == AssetRegistryErrorCode.LOCK_INTEGRITY_INVALID
    )

    installation_store = PostgresInstallationStore(scoped_connect)
    draft = installation_store.create_draft(
        org_id="org-a",
        project_id="project-a",
        request=CreateInstallationRequest.model_validate(
            {
                "compositionId": lock.composition_id,
                "lockRevision": 1,
                "overlayRevision": "overlay-w4-v1",
                "displayName": "W4 draft installation",
            }
        ),
        requested_by="w4-requester",
    )
    assert draft.state == "draft"
    assert draft.current_revision == 1
    assert draft.etag_version == 1
    with pytest.raises(AssetRegistryError) as installation_cross_tenant:
        installation_store.get_installation(
            org_id="org-b",
            project_id="project-a",
            installation_id=draft.installation_id,
        )
    assert installation_cross_tenant.value.code == AssetRegistryErrorCode.NOT_FOUND

    with scoped_connect() as connection:
        current = installation_store.lock_for_cas(
            connection,
            org_id="org-a",
            project_id="project-a",
            installation_id=draft.installation_id,
            expected_etag_version=1,
        )
        assert current.installation_id == draft.installation_id
        connection.rollback()
    with scoped_connect() as connection:
        with pytest.raises(AssetRegistryError) as stale_cas:
            installation_store.lock_for_cas(
                connection,
                org_id="org-a",
                project_id="project-a",
                installation_id=draft.installation_id,
                expected_etag_version=2,
            )
        connection.rollback()
    assert stale_cas.value.code == AssetRegistryErrorCode.REVISION_CONFLICT

    request_hash = command_request_hash(
        subject="w4-requester",
        path_params={"installationId": draft.installation_id},
        body={},
        if_match='"1"',
    )
    calls = 0

    def command_handler(_connection):
        nonlocal calls
        calls += 1
        return CommandResult(
            status_code=200,
            response_json={"installationId": draft.installation_id},
            response_etag='"1"',
        )

    first = installation_store.execute_idempotent(
        org_id="org-a",
        project_id="project-a",
        operation="w4-draft-check",
        idempotency_key="w4-key",
        subject="w4-requester",
        request_hash=request_hash,
        handler=command_handler,
    )
    replayed = installation_store.execute_idempotent(
        org_id="org-a",
        project_id="project-a",
        operation="w4-draft-check",
        idempotency_key="w4-key",
        subject="w4-requester",
        request_hash=request_hash,
        handler=command_handler,
    )
    assert calls == 1
    assert first.replayed is False
    assert replayed.replayed is True
    assert replayed.response_json == first.response_json

    with pytest.raises(AssetRegistryError) as idempotency_conflict:
        installation_store.execute_idempotent(
            org_id="org-a",
            project_id="project-a",
            operation="w4-draft-check",
            idempotency_key="w4-key",
            subject="w4-requester",
            request_hash=canonical_sha256({"different": "command"}),
            handler=command_handler,
        )
    assert (
        idempotency_conflict.value.code == AssetRegistryErrorCode.IDEMPOTENCY_CONFLICT
    )


@pytest.mark.parametrize(
    ("table", "trigger", "column"),
    [
        (
            "bundle_composition",
            "trg_bundle_composition_immutable",
            "registry_snapshot_hash",
        ),
        (
            "bundle_composition_lock",
            "trg_bundle_composition_lock_immutable",
            "lock_hash",
        ),
    ],
)
def test_persisted_snapshot_and_lock_tampering_map_to_fixed_corruption_error(
    core_database,
    table: str,
    trigger: str,
    column: str,
) -> None:
    scoped_connect = core_database
    store, _, _, _, lock = _persist_lock(scoped_connect)
    with scoped_connect() as connection:
        connection.execute(
            sql.SQL("ALTER TABLE {} DISABLE TRIGGER {}").format(
                sql.Identifier(table), sql.Identifier(trigger)
            )
        )
        connection.execute(
            sql.SQL("UPDATE {} SET {} = %s").format(
                sql.Identifier(table), sql.Identifier(column)
            ),
            (canonical_sha256({"tampered": table}),),
        )
        connection.execute(
            sql.SQL("ALTER TABLE {} ENABLE TRIGGER {}").format(
                sql.Identifier(table), sql.Identifier(trigger)
            )
        )
        connection.commit()

    with pytest.raises(AssetRegistryError) as caught:
        store.get_lock(
            org_id="org-a",
            project_id="project-a",
            composition_id=lock.composition_id,
        )
    assert caught.value.code == AssetRegistryErrorCode.LOCK_INTEGRITY_CORRUPT
    assert str(caught.value) == "stored composition lock failed integrity verification"


def test_tampered_idempotency_receipt_maps_to_fixed_corruption_error(
    core_database,
) -> None:
    scoped_connect = core_database
    store = PostgresInstallationStore(scoped_connect)
    request_hash = command_request_hash(
        subject="w4-subject",
        path_params={},
        body={"action": "probe"},
        if_match=None,
    )
    store.execute_idempotent(
        org_id="org-a",
        project_id="project-a",
        operation="w4-receipt",
        idempotency_key="receipt-key",
        subject="w4-subject",
        request_hash=request_hash,
        handler=lambda _connection: CommandResult(
            status_code=201,
            response_json={"created": True},
        ),
    )
    with scoped_connect() as connection:
        connection.execute(
            "ALTER TABLE bundle_installation_command "
            "DISABLE TRIGGER trg_bundle_installation_command_immutable"
        )
        connection.execute(
            "UPDATE bundle_installation_command SET subject = 'forged-subject'"
        )
        connection.execute(
            "ALTER TABLE bundle_installation_command "
            "ENABLE TRIGGER trg_bundle_installation_command_immutable"
        )
        connection.commit()

    with pytest.raises(AssetRegistryError) as caught:
        store.execute_idempotent(
            org_id="org-a",
            project_id="project-a",
            operation="w4-receipt",
            idempotency_key="receipt-key",
            subject="w4-subject",
            request_hash=request_hash,
            handler=lambda _connection: CommandResult(
                status_code=500,
                response_json={"mustNotRun": True},
            ),
        )
    assert caught.value.code == AssetRegistryErrorCode.LOCK_INTEGRITY_CORRUPT
    assert str(caught.value) == "stored composition lock failed integrity verification"
