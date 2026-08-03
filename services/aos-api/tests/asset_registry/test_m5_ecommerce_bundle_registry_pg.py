"""M5-1 real-PostgreSQL publication and restart snapshot for ecommerce bundles."""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from psycopg import sql

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import DutySeparationRequiredError
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import (
    REQUIRED_RELEASE_EVIDENCE,
    ReleasePolicy,
)
from aos_api.asset_registry.signature import TrustRoot
from aos_api.db import connect
from tests.asset_registry.m5_bundle_support import (
    M5_BUNDLE_FIXTURES,
    RuntimeSignedM5Bundle,
    copy_and_sign_m5_bundles,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATHS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
)
CREATE_ROLES = {"developer"}
PUBLISH_ROLES = {"asset-publisher"}
AUTHOR = "m5-author"
VALIDATOR = "m5-validator"
PUBLISHER = "m5-publisher"

ConnectFactory = Callable[[], AbstractContextManager[Any]]


def _load_migration(path: Path, index: int) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"m5_registry_migration_{index}", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements() -> list[str]:
    statements: list[str] = []
    for index, path in enumerate(MIGRATION_PATHS):
        module = _load_migration(path, index)
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value = []
        with (
            patch.object(module.op, "execute", statements.append),
            patch.object(module.op, "get_bind", return_value=connection),
        ):
            module.upgrade()
    return statements


@pytest.fixture()
def m5_registry_database() -> Iterator[ConnectFactory]:
    schema = f"m5_registry_{uuid.uuid4().hex}"
    created = False
    try:
        with connect() as connection:
            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema))
            )
            created = True
            connection.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            for statement in _upgrade_statements():
                connection.execute(statement)
            connection.commit()
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
    def scoped_connect() -> Iterator[Any]:
        with connect() as connection:
            connection.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield connection

    try:
        yield scoped_connect
    finally:
        if created:
            with connect() as cleanup:
                cleanup.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
                cleanup.commit()


def _database_clock(connect_factory: ConnectFactory) -> datetime:
    with connect_factory() as connection:
        row = connection.execute("SELECT clock_timestamp() AS checked_at").fetchone()
    assert row is not None
    checked_at = row["checked_at"]
    assert isinstance(checked_at, datetime) and checked_at.utcoffset() is not None
    return checked_at


def _assert_release_evidence(
    record: dict[str, Any],
    *,
    signed_bundle: RuntimeSignedM5Bundle,
    trust_root: TrustRoot,
    checked_at: datetime,
) -> None:
    expected_types = {item.value for item in REQUIRED_RELEASE_EVIDENCE}
    evidence_by_type = {item["type"]: item for item in record["evidence"]}

    assert set(evidence_by_type) == expected_types
    assert len(record["evidence"]) == len(expected_types)
    assert all(item["status"] == "valid" for item in record["evidence"])
    assert all(item["revokedAt"] is None for item in record["evidence"])
    assert all(
        datetime.fromisoformat(item["observedAt"]) <= checked_at
        for item in record["evidence"]
    )
    assert all(
        item["expiresAt"] is None
        or datetime.fromisoformat(item["expiresAt"]) > checked_at
        for item in record["evidence"]
    )

    assert evidence_by_type["manifest_validation"]["artifactHash"] == (
        canonical_sha256(
            signed_bundle.signed.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            )
        )
    )
    assert evidence_by_type["content_hash"]["artifactHash"] == record["contentHash"]
    assert evidence_by_type["signature_verification"]["artifactHash"] == (
        canonical_sha256(
            signed_bundle.signed.signature.model_dump(
                mode="json", by_alias=True, exclude_none=False
            )
        )
    )
    assert (
        evidence_by_type["signature_verification"]["metadata"]["trustRootRevision"]
        == trust_root.revision
    )
    assert (
        datetime.fromisoformat(evidence_by_type["signature_verification"]["expiresAt"])
        == trust_root.not_after
    )

    artifacts = {item["relativePath"]: item for item in record["artifacts"]}
    assert (
        evidence_by_type["sbom"]["artifactHash"]
        == artifacts["evidence/sbom.json"]["digest"]
    )
    assert (
        evidence_by_type["bundle_evals"]["artifactHash"]
        == artifacts["evidence/bundle-evals.json"]["digest"]
    )


def test_four_m5_bundles_publish_and_survive_registry_restart(
    m5_registry_database: ConnectFactory,
    tmp_path: Path,
) -> None:
    db_clock = _database_clock(m5_registry_database)
    prepared = copy_and_sign_m5_bundles(
        tmp_path / "runtime-bundles",
        signed_at=db_clock,
    )
    service = RegistryService(
        store=PostgresRegistryStore(m5_registry_database),
        loader=prepared.loader,
        clock=lambda: _database_clock(m5_registry_database),
        trust_roots=prepared.trust_roots,
    )
    published_by_id: dict[str, dict[str, Any]] = {}

    for fixture in M5_BUNDLE_FIXTURES:
        signed_bundle = prepared.by_id(fixture.bundle_id)
        manifest = signed_bundle.signed.manifest
        service.create_bundle(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            kind=manifest.kind,
            display_name=manifest.metadata.display_name,
            actor=AUTHOR,
            roles=CREATE_ROLES,
            publisher_scopes={"aos"},
        )
        draft = service.create_version(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            source_ref=fixture.source_ref,
            actor=AUTHOR,
            roles=CREATE_ROLES,
            publisher_scopes={"aos"},
        )

        assert draft["status"] == "draft"
        assert draft["contentHash"] == signed_bundle.unsigned.content_hash
        assert draft["contentHash"] == signed_bundle.signed.content_hash
        assert draft["signature"]["keyId"] == prepared.trust_root.key_id
        assert [item["relativePath"] for item in draft["artifacts"]] == [
            item.relative_path for item in signed_bundle.signed.artifacts
        ]
        assert "bundle.signature.json" not in {
            item["relativePath"] for item in draft["artifacts"]
        }
        assert draft["lifecycleEvents"] == []

        validated = service.validate(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            version="1.0.0",
            actor=VALIDATOR,
            roles=CREATE_ROLES,
            publisher_scopes={"aos"},
        )
        assert validated["status"] == "validated"
        assert [event["sequence"] for event in validated["lifecycleEvents"]] == [1]

        for invalid_publisher in (AUTHOR, VALIDATOR):
            with pytest.raises(DutySeparationRequiredError):
                service.publish(
                    publisher="aos",
                    bundle_id=fixture.bundle_id,
                    version="1.0.0",
                    actor=invalid_publisher,
                    roles=PUBLISH_ROLES,
                    publisher_scopes={"aos"},
                )
            unchanged = service.get_version(
                publisher="aos",
                bundle_id=fixture.bundle_id,
                version="1.0.0",
            )
            assert unchanged["status"] == "validated"
            assert [event["sequence"] for event in unchanged["lifecycleEvents"]] == [1]

        published = service.publish(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            version="1.0.0",
            actor=PUBLISHER,
            roles=PUBLISH_ROLES,
            publisher_scopes={"aos"},
        )
        assert published["status"] == "published"
        assert [event["sequence"] for event in published["lifecycleEvents"]] == [
            1,
            2,
        ]
        assert [event["actor"] for event in published["lifecycleEvents"]] == [
            VALIDATOR,
            PUBLISHER,
        ]
        assert [
            (event["fromStatus"], event["toStatus"])
            for event in published["lifecycleEvents"]
        ] == [("draft", "validated"), ("validated", "published")]
        assert all(
            event["evidenceRevision"].startswith("sha256:")
            for event in published["lifecycleEvents"]
        )
        _assert_release_evidence(
            published,
            signed_bundle=signed_bundle,
            trust_root=prepared.trust_root,
            checked_at=_database_clock(m5_registry_database),
        )
        published_by_id[fixture.bundle_id] = published

    restarted_store = PostgresRegistryStore(m5_registry_database)
    restarted_service = RegistryService(
        store=restarted_store,
        loader=prepared.loader,
        clock=lambda: _database_clock(m5_registry_database),
        trust_roots=prepared.trust_roots,
    )
    for fixture in M5_BUNDLE_FIXTURES:
        expected = published_by_id[fixture.bundle_id]
        persisted = restarted_store.get_version(
            fixture.bundle_id,
            "1.0.0",
            "aos",
        )
        public = restarted_service.get_version(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            version="1.0.0",
        )
        assert persisted["status"] == public["status"] == "published"
        assert (
            persisted["contentHash"] == public["contentHash"] == expected["contentHash"]
        )
        assert persisted["signature"] == expected["signature"]
        assert persisted["dependencies"] == expected["dependencies"]
        assert persisted["artifacts"] == expected["artifacts"]
        assert persisted["evidence"] == expected["evidence"]

    snapshot_reader = RegistrySnapshotReader(
        connect_factory=m5_registry_database,
        release_policy=ReleasePolicy(trust_roots=prepared.trust_roots),
    )
    snapshot = snapshot_reader.read()
    restarted_snapshot = RegistrySnapshotReader(
        connect_factory=m5_registry_database,
        release_policy=ReleasePolicy(trust_roots=prepared.trust_roots),
    ).read()

    expected_ids = [
        "domain.ecommerce.core",
        "platform.ecommerce.niushop",
        "solution.ecommerce.growth",
        "solution.ecommerce.operations-base",
    ]
    assert [candidate.id for candidate in snapshot.candidates] == expected_ids
    assert restarted_snapshot.candidates == snapshot.candidates
    assert restarted_snapshot.snapshot_hash == snapshot.snapshot_hash

    for candidate in snapshot.candidates:
        expected = published_by_id[candidate.id]
        signed_bundle = prepared.by_id(candidate.id)
        signature_evidence = next(
            item
            for item in expected["evidence"]
            if item["type"] == "signature_verification"
        )
        assert candidate.publisher == "aos"
        assert candidate.version == "1.0.0"
        assert candidate.kind == signed_bundle.signed.manifest.kind
        assert candidate.manifest == signed_bundle.signed.manifest
        assert candidate.content_hash == expected["contentHash"]
        assert candidate.signature_fingerprint == signature_evidence["artifactHash"]
        assert candidate.release_evidence_revision.startswith("sha256:")
        assert candidate.optional_dependencies == []
        assert candidate.conflicts == []
        assert candidate.contributions == []
        if candidate.id == "domain.ecommerce.core":
            assert candidate.dependencies == []
        else:
            assert [
                (dependency.publisher, dependency.id, dependency.version)
                for dependency in candidate.dependencies
            ] == [("aos", "domain.ecommerce.core", ">=1.0.0 <2.0.0")]
