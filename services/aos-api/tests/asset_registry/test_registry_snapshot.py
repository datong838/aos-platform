from __future__ import annotations

import base64
import importlib.util
import json
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import (
    BundleEvidenceType,
    BundleManifest,
    BundleSignature,
    LoadedBundle,
)
from aos_api.asset_registry.errors import AssetRegistryError, AssetRegistryErrorCode
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import (
    REQUIRED_RELEASE_EVIDENCE,
    ReleasePolicy,
)
from aos_api.asset_registry.signature import FrozenTrustRootProvider, TrustRoot
from aos_api.db import connect

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
)
NOW = datetime.now(UTC).replace(microsecond=0)


class Roots:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], TrustRoot] = {}
        self.private_keys: dict[str, Ed25519PrivateKey] = {}
        self.snapshot_hook: Callable[[], None] | None = None

    def add(self, root: TrustRoot) -> None:
        self.items[(root.publisher, root.key_id)] = root

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        return self.items.get((publisher, key_id))

    def snapshot(self) -> FrozenTrustRootProvider:
        frozen = FrozenTrustRootProvider(self.items)
        if self.snapshot_hook is not None:
            self.snapshot_hook()
        return frozen


class StaticLoader:
    def __init__(self, loaded: LoadedBundle, roots: Roots) -> None:
        self.loaded = loaded
        self.trust_roots = roots

    def load(self, source_ref: str) -> LoadedBundle:
        assert source_ref == self.loaded.source_ref
        return self.loaded


def _load_migration(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements() -> list[str]:
    statements: list[str] = []
    for index, path in enumerate(MIGRATIONS):
        module = _load_migration(path, f"registry_snapshot_migration_{index}")
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value = []
        with (
            patch.object(module.op, "execute", statements.append),
            patch.object(module.op, "get_bind", return_value=connection),
        ):
            module.upgrade()
    return statements


@pytest.fixture()
def registry_database():
    schema = f"asset_registry_snapshot_{uuid.uuid4().hex}"
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


def _manifest(*, publisher: str, bundle_id: str, version: str) -> BundleManifest:
    return BundleManifest.model_validate(
        {
            "apiVersion": "aos.dev/v1alpha1",
            "kind": "SolutionPack",
            "metadata": {
                "id": bundle_id,
                "version": version,
                "displayName": f"{publisher} {bundle_id}",
                "publisher": publisher,
                "license": "internal",
            },
            "spec": {
                "platformApi": ">=1.7.0 <2.0.0",
                "dependencies": [{"id": "domain.foundation", "version": "^1.0.0"}],
                "optionalDependencies": [],
                "conflicts": [],
                "exports": {},
                "capabilities": {
                    "provides": [f"capability.{publisher}"],
                    "requires": [],
                },
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


def _signed_loaded(
    *,
    roots: Roots,
    publisher: str,
    bundle_id: str,
    version: str,
) -> LoadedBundle:
    key_id = f"{publisher}-release-key"
    private_key = roots.private_keys.setdefault(publisher, Ed25519PrivateKey.generate())
    root_revision = canonical_sha256(
        {"publisher": publisher, "keyId": key_id, "revision": 1}
    )
    root = TrustRoot(
        publisher=publisher,
        key_id=key_id,
        public_key=private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
        revision=root_revision,
        not_before=NOW - timedelta(days=1),
        not_after=NOW + timedelta(days=7),
    )
    roots.add(root)
    manifest = _manifest(publisher=publisher, bundle_id=bundle_id, version=version)
    source_ref = f"bundle://fixtures/{publisher}/{bundle_id}/{version}"
    artifacts = [
        {
            "relativePath": "content/config.json",
            "artifactRef": f"{source_ref}/content/config.json",
            "digest": canonical_sha256({"fixture": bundle_id}),
            "size": 2,
            "mediaType": "application/json",
        }
    ]
    descriptor = {
        "manifest": manifest.model_dump(mode="json", by_alias=True, exclude_none=False),
        "artifacts": [
            {
                "relativePath": item["relativePath"],
                "digest": item["digest"],
                "size": item["size"],
                "mediaType": item["mediaType"],
            }
            for item in artifacts
        ],
    }
    content_hash = canonical_sha256(descriptor)
    signature = BundleSignature.model_validate(
        {
            "algorithm": "Ed25519",
            "keyId": key_id,
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
            {"publisher": publisher, "type": evidence_type.value}
        )
        if evidence_type == BundleEvidenceType.CONTENT_HASH:
            artifact_hash = content_hash
        elif evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION:
            artifact_hash = signature_hash
        evidence.append(
            {
                "type": evidence_type,
                "artifactRef": (
                    f"bundle://fixtures/{publisher}/{bundle_id}/"
                    f"evidence/{evidence_type.value}.json"
                ),
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
                    {"trustRootRevision": root_revision}
                    if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION
                    else {}
                ),
            }
        )
    return LoadedBundle.model_validate(
        {
            "sourceRef": source_ref,
            "manifest": manifest,
            "artifacts": artifacts,
            "evidence": evidence,
            "contentHash": content_hash,
            "signature": signature,
            "loadedAt": NOW,
        }
    )


def _publish(
    store: PostgresRegistryStore,
    roots: Roots,
    *,
    publisher: str,
    bundle_id: str,
    version: str,
    create_bundle: bool = True,
) -> None:
    loaded = _signed_loaded(
        roots=roots, publisher=publisher, bundle_id=bundle_id, version=version
    )
    service = RegistryService(
        store=store,
        loader=StaticLoader(loaded, roots),
        clock=lambda: NOW,
        trust_roots=roots,
    )
    if create_bundle:
        service.create_bundle(
            publisher=publisher,
            bundle_id=bundle_id,
            kind="SolutionPack",
            display_name=f"{publisher} {bundle_id}",
            actor=f"{publisher}-author",
            roles={"developer"},
            publisher_scopes={publisher},
        )
    service.create_version(
        bundle_id=bundle_id,
        source_ref=loaded.source_ref,
        actor=f"{publisher}-author",
        roles={"developer"},
        publisher=publisher,
        publisher_scopes={publisher},
    )
    service.validate(
        bundle_id=bundle_id,
        version=version,
        actor=f"{publisher}-validator",
        roles={"developer"},
        publisher=publisher,
        publisher_scopes={publisher},
    )
    service.publish(
        bundle_id=bundle_id,
        version=version,
        actor=f"{publisher}-publisher",
        roles={"asset-publisher"},
        publisher=publisher,
        publisher_scopes={publisher},
    )


def _reader(scoped_connect, roots: Roots, *, clock=None) -> RegistrySnapshotReader:
    return RegistrySnapshotReader(
        connect_factory=scoped_connect,
        clock=clock,
        release_policy=ReleasePolicy(trust_roots=roots),
    )


def test_snapshot_empty_registry_is_real_and_hash_stable(registry_database) -> None:
    _, scoped_connect = registry_database
    roots = Roots()

    first = _reader(scoped_connect, roots).read()
    second = _reader(scoped_connect, roots).read()

    assert first.candidates == []
    assert first.snapshot_hash == second.snapshot_hash
    assert first.checked_at.utcoffset() is not None


def test_snapshot_derives_sorted_candidates_and_signed_indexes(
    registry_database,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="partner",
        bundle_id="solution.same",
        version="2.0.0",
    )
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.same",
        version="1.0.0",
    )
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.same",
        version="1.1.0",
        create_bundle=False,
    )

    snapshot = _reader(scoped_connect, roots).read()

    assert [
        (item.publisher, item.id, item.version) for item in snapshot.candidates
    ] == [
        ("aos", "solution.same", "1.0.0"),
        ("aos", "solution.same", "1.1.0"),
        ("partner", "solution.same", "2.0.0"),
    ]
    candidate = snapshot.candidates[0]
    assert candidate.dependencies[0].publisher == "aos"
    assert candidate.capabilities.provides == ["capability.aos"]
    assert candidate.permissions.roles == ["viewer"]
    assert candidate.signature_fingerprint.startswith("sha256:")
    assert candidate.release_evidence_revision.startswith("sha256:")
    assert snapshot.snapshot_hash == canonical_sha256(snapshot.hash_payload_dump())


def test_snapshot_enforces_real_repeatable_read_read_only_transaction(
    registry_database,
) -> None:
    _, scoped_connect = registry_database
    roots = Roots()

    def checked_clock(conn):
        isolation = conn.execute("SHOW transaction_isolation").fetchone()[
            "transaction_isolation"
        ]
        read_only = conn.execute("SHOW transaction_read_only").fetchone()[
            "transaction_read_only"
        ]
        assert isolation == "repeatable read"
        assert read_only == "on"
        return conn.execute("SELECT transaction_timestamp() AS checked_at").fetchone()[
            "checked_at"
        ]

    assert _reader(scoped_connect, roots, clock=checked_clock).read().candidates == []


@pytest.mark.parametrize("transition", ["expired", "revoked"])
def test_snapshot_concurrent_evidence_change_never_mixes_transaction_views(
    registry_database,
    transition: str,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.concurrent",
        version="1.0.0",
    )
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.stable",
        version="1.0.0",
    )
    snapshot_started = Event()
    evidence_changed = Event()

    def blocking_clock(conn):
        checked_at = conn.execute(
            "SELECT transaction_timestamp() AS checked_at"
        ).fetchone()["checked_at"]
        snapshot_started.set()
        assert evidence_changed.wait(timeout=10)
        return checked_at

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _reader(scoped_connect, roots, clock=blocking_clock).read
        )
        assert snapshot_started.wait(timeout=10)
        try:
            with scoped_connect() as conn:
                if transition == "expired":
                    conn.execute(
                        """
                        UPDATE asset_bundle_evidence
                           SET status = 'expired',
                               updated_at = clock_timestamp() + INTERVAL '1 second',
                               updated_by = 'security-monitor',
                               status_reason = 'evidence expired'
                             WHERE evidence_type = 'sbom'
                               AND version_pk = (
                                 SELECT v.version_pk
                                   FROM asset_bundle_version AS v
                                   JOIN asset_bundle AS b
                                     ON b.bundle_pk = v.bundle_pk
                                  WHERE b.publisher = 'aos'
                                    AND b.bundle_id = 'solution.concurrent'
                                    AND v.version = '1.0.0'
                               )
                        """
                    )
                else:
                    conn.execute(
                        """
                        UPDATE asset_bundle_evidence
                           SET status = 'revoked',
                               revoked_at = clock_timestamp(),
                               updated_at = clock_timestamp() + INTERVAL '1 second',
                               updated_by = 'security-monitor',
                               status_reason = 'evidence revoked'
                             WHERE evidence_type = 'sbom'
                               AND version_pk = (
                                 SELECT v.version_pk
                                   FROM asset_bundle_version AS v
                                   JOIN asset_bundle AS b
                                     ON b.bundle_pk = v.bundle_pk
                                  WHERE b.publisher = 'aos'
                                    AND b.bundle_id = 'solution.concurrent'
                                    AND v.version = '1.0.0'
                               )
                        """
                    )
                conn.commit()
        finally:
            evidence_changed.set()
        before_change = future.result(timeout=10)

    after_change = _reader(scoped_connect, roots).read()
    assert len(before_change.candidates) == 2
    assert [item.id for item in after_change.candidates] == ["solution.stable"]


def test_snapshot_manifest_damage_precedes_stale_evidence_in_real_postgres(
    registry_database,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.damaged-stale",
        version="1.0.0",
    )
    with scoped_connect() as conn:
        conn.execute(
            "ALTER TABLE asset_bundle_version "
            "DISABLE TRIGGER trg_asset_bundle_version_guard"
        )
        conn.execute(
            """
            UPDATE asset_bundle_version
               SET manifest_json = jsonb_set(
                     manifest_json,
                     '{metadata,displayName}',
                     '"Tampered"'::JSONB
                   )
            """
        )
        conn.execute(
            "ALTER TABLE asset_bundle_version "
            "ENABLE TRIGGER trg_asset_bundle_version_guard"
        )
        conn.execute(
            """
            UPDATE asset_bundle_evidence
               SET status = 'expired',
                   updated_at = clock_timestamp() + INTERVAL '1 second',
                   updated_by = 'w1-adversary',
                   status_reason = 'stale evidence with damaged manifest'
             WHERE evidence_type = 'sbom'
            """
        )
        conn.commit()

    with pytest.raises(AssetRegistryError) as caught:
        _reader(scoped_connect, roots).read()

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


def test_snapshot_crypto_damage_precedes_revoked_evidence_in_real_postgres(
    registry_database,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.crypto-revoked",
        version="1.0.0",
    )
    with scoped_connect() as conn:
        row = conn.execute("SELECT signature FROM asset_bundle_version").fetchone()
        assert row is not None
        signature_json = dict(row["signature"])
        signature_json["signature"] = base64.b64encode(b"x" * 64).decode("ascii")
        signature = BundleSignature.model_validate_json(json.dumps(signature_json))
        signature_json = signature.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
        )
        signature_hash = canonical_sha256(signature_json)

        conn.execute(
            "ALTER TABLE asset_bundle_version "
            "DISABLE TRIGGER trg_asset_bundle_version_guard"
        )
        conn.execute(
            "ALTER TABLE asset_bundle_evidence "
            "DISABLE TRIGGER trg_asset_bundle_evidence_guard"
        )
        conn.execute(
            "UPDATE asset_bundle_version SET signature = %s",
            (Jsonb(signature_json),),
        )
        conn.execute(
            """
            UPDATE asset_bundle_evidence
               SET artifact_hash = %s,
                   updated_at = clock_timestamp() + INTERVAL '1 second',
                   updated_by = 'w1-adversary',
                   status_reason = 'tampered signature envelope'
             WHERE evidence_type = 'signature_verification'
            """,
            (signature_hash,),
        )
        conn.execute(
            """
            UPDATE asset_bundle_evidence
               SET status = 'revoked',
                   revoked_at = clock_timestamp(),
                   updated_at = clock_timestamp() + INTERVAL '1 second',
                   updated_by = 'w1-adversary',
                   status_reason = 'revoked evidence with invalid signature'
             WHERE evidence_type = 'sbom'
            """
        )
        conn.execute(
            "ALTER TABLE asset_bundle_evidence "
            "ENABLE TRIGGER trg_asset_bundle_evidence_guard"
        )
        conn.execute(
            "ALTER TABLE asset_bundle_version "
            "ENABLE TRIGGER trg_asset_bundle_version_guard"
        )
        conn.commit()

    with pytest.raises(AssetRegistryError) as caught:
        _reader(scoped_connect, roots).read()

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


def test_snapshot_candidate_limit_ignores_ineligible_rows_before_valid_candidate(
    registry_database,
    monkeypatch,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    invalid_ids = (
        "solution.aaa-invalid",
        "solution.aab-invalid",
        "solution.aac-invalid",
    )
    for bundle_id in (*invalid_ids, "solution.zzz-valid"):
        _publish(
            store,
            roots,
            publisher="aos",
            bundle_id=bundle_id,
            version="1.0.0",
        )
    with scoped_connect() as conn:
        conn.execute(
            """
            UPDATE asset_bundle_evidence AS e
               SET status = 'expired',
                   updated_at = clock_timestamp() + INTERVAL '1 second',
                   updated_by = 'w1-monitor',
                   status_reason = 'ineligible candidate must not consume budget'
              FROM asset_bundle_version AS v
              JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
             WHERE e.version_pk = v.version_pk
               AND b.bundle_id = ANY(%s)
               AND e.evidence_type = 'sbom'
            """,
            (list(invalid_ids),),
        )
        conn.commit()
    monkeypatch.setattr(
        "aos_api.asset_registry.registry_snapshot.MAX_SNAPSHOT_CANDIDATES", 1
    )

    snapshot = _reader(scoped_connect, roots).read()

    assert [item.id for item in snapshot.candidates] == ["solution.zzz-valid"]


def test_snapshot_candidate_limit_fails_closed_in_real_postgres(
    registry_database,
    monkeypatch,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.one",
        version="1.0.0",
    )
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.two",
        version="1.0.0",
    )
    monkeypatch.setattr(
        "aos_api.asset_registry.registry_snapshot.MAX_SNAPSHOT_CANDIDATES", 1
    )

    with pytest.raises(AssetRegistryError) as caught:
        _reader(scoped_connect, roots).read()

    assert caught.value.code == AssetRegistryErrorCode.RESOLUTION_LIMIT_EXCEEDED
    assert caught.value.details == {
        "resource": "snapshot_candidates",
        "limit": 1,
        "observed": 2,
    }


def test_snapshot_uses_one_frozen_view_across_two_publishers_and_next_read_excludes_rotated_roots(
    registry_database,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.aos",
        version="1.0.0",
    )
    _publish(
        store,
        roots,
        publisher="partner",
        bundle_id="solution.partner",
        version="1.0.0",
    )
    aos_identity = ("aos", "aos-release-key")
    partner_identity = ("partner", "partner-release-key")
    aos_root = roots.items[aos_identity]
    partner_root = roots.items[partner_identity]

    def rotate_after_freeze() -> None:
        roots.items[aos_identity] = TrustRoot(
            publisher=aos_root.publisher,
            key_id=aos_root.key_id,
            public_key=aos_root.public_key,
            revision=canonical_sha256({"publisher": "aos", "revision": 2}),
            not_before=aos_root.not_before,
            not_after=aos_root.not_after,
        )
        roots.items[partner_identity] = TrustRoot(
            publisher=partner_root.publisher,
            key_id=partner_root.key_id,
            public_key=partner_root.public_key,
            revision=partner_root.revision,
            not_before=partner_root.not_before,
            not_after=partner_root.not_after,
            revoked_at=NOW,
        )
        roots.snapshot_hook = None

    roots.snapshot_hook = rotate_after_freeze

    before_rotation = _reader(scoped_connect, roots).read()
    after_rotation = _reader(scoped_connect, roots).read()

    assert [(item.publisher, item.id) for item in before_rotation.candidates] == [
        ("aos", "solution.aos"),
        ("partner", "solution.partner"),
    ]
    assert after_rotation.candidates == []


def test_snapshot_duplicate_signature_evidence_is_global_even_when_one_is_expired(
    registry_database,
) -> None:
    store, scoped_connect = registry_database
    roots = Roots()
    _publish(
        store,
        roots,
        publisher="aos",
        bundle_id="solution.duplicate-signature",
        version="1.0.0",
    )
    with scoped_connect() as conn:
        conn.execute(
            "ALTER TABLE asset_bundle_evidence "
            "DISABLE TRIGGER trg_asset_bundle_evidence_guard"
        )
        conn.execute(
            """
            INSERT INTO asset_bundle_evidence (
              version_pk,
              evidence_type,
              artifact_ref,
              artifact_hash,
              status,
              observed_at,
              expires_at,
              revoked_at,
              metadata,
              updated_at,
              updated_by,
              status_reason
            )
            SELECT version_pk,
                   evidence_type,
                   artifact_ref || '.duplicate',
                   artifact_hash,
                   'expired',
                   observed_at,
                   %s,
                   NULL,
                   metadata,
                   clock_timestamp(),
                   'w1-adversary',
                   'duplicate signature evidence'
              FROM asset_bundle_evidence
             WHERE evidence_type = 'signature_verification'
            """,
            (NOW,),
        )
        conn.execute(
            "ALTER TABLE asset_bundle_evidence "
            "ENABLE TRIGGER trg_asset_bundle_evidence_guard"
        )
        conn.commit()

    with pytest.raises(AssetRegistryError) as caught:
        _reader(scoped_connect, roots).read()

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


@pytest.mark.parametrize("failure", ["unsupported", "outage"])
def test_snapshot_fails_closed_when_provider_cannot_freeze_one_view(
    registry_database,
    failure: str,
) -> None:
    _, scoped_connect = registry_database

    class DynamicProvider:
        def get_trust_root(
            self,
            *,
            publisher: str,
            key_id: str,
        ) -> TrustRoot | None:
            return None

    class OutageProvider(DynamicProvider):
        def snapshot(self):
            raise RuntimeError("private provider outage")

    provider = OutageProvider() if failure == "outage" else DynamicProvider()

    with pytest.raises(AssetRegistryError) as caught:
        RegistrySnapshotReader(
            connect_factory=scoped_connect,
            release_policy=ReleasePolicy(trust_roots=provider),
        ).read()

    assert caught.value.code == AssetRegistryErrorCode.TRUST_ROOT_UNAVAILABLE
    assert "private provider outage" not in str(caught.value)
