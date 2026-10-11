"""Real isolated publication/install prerequisite; never production authority."""

import json
import os
from contextlib import contextmanager

import psycopg
import pytest
from psycopg import IsolationLevel, sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import InstallationResponse, StoredCompositionLock
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.errors import RegistrySnapshotStaleError, VerificationFailedError
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentReleaseEvidenceBlocked,
    _read_unique_active_in_transaction,
)
from aos_api.tenant_scope import TenantScope
from tests.asset_registry import m5_control_support as support
from tests.asset_registry.test_m5_ecommerce_composition_installation_pg import (
    OVERLAY_FIXTURE,
    _three_leaf_request,
)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    # Explicit clone boundary: a missing endpoint is a failure, never a skip.
    target = conninfo_to_dict(os.environ["AOS_DATABASE_URL"])
    assert (target["host"], target["port"], target["user"]) == ("127.0.0.1", "18431", "aos_app")
    assert target["dbname"].startswith("aos_test_") and target["dbname"].endswith("_ti4_test")
    with psycopg.connect(os.environ["AOS_DATABASE_URL"], row_factory=dict_row) as conn:
        assert str(conn.execute("SELECT system_identifier FROM pg_control_system()").fetchone()["system_identifier"]) == "7695416748450308141"
    monkeypatch.setattr(support, "M5_ORG_ID", "org-org")
    monkeypatch.setattr(support, "M5_PROJECT_ID", "dev-project")
    with support.m5_control_runtime(tmp_path / "signed-test-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        resolved = runtime.resolve(_three_leaf_request(snapshot), actor="fixture-maker", idempotency_key="qyh-resolve")
        lock = StoredCompositionLock.model_validate_json(json.dumps(resolved.response_json))
        receipts = runtime.install_to_active(
            lock=lock,
            overlay_revision=canonical_sha256(json.loads(OVERLAY_FIXTURE.read_text())),
            maker="fixture-maker", checker="fixture-checker", idempotency_prefix="qyh-install",
        )
        active = InstallationResponse.model_validate_json(json.dumps(receipts[-1].response_json))
        assert active.state == "active" and active.current_revision == 5
        assert all(not receipt.replayed for receipt in receipts)
        with runtime.connect_factory() as conn:
            schema = conn.execute("SELECT current_schema() AS schema").fetchone()["schema"]
        yield runtime, active, schema


def read_growth(runtime, conn):
    bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
    return _read_unique_active_in_transaction(
        conn, scope=TenantScope("org-org", "dev-project"), publisher="aos",
        bundle_id=bundle.manifest.metadata.id, version=bundle.manifest.metadata.version,
        content_hash=bundle.content_hash,
        release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots),
        loader=runtime.prepared.loader,
    )


def test_original_second_installation_is_ambiguous(installed):
    runtime, _, _ = installed
    resolved = runtime.resolve(
        _three_leaf_request(runtime.snapshot_reader.read()),
        actor="fixture-maker", idempotency_key="qyh-second-resolve",
    )
    lock = StoredCompositionLock.model_validate_json(json.dumps(resolved.response_json))
    runtime.install_to_active(
        lock=lock, overlay_revision=canonical_sha256(json.loads(OVERLAY_FIXTURE.read_text())),
        maker="fixture-maker", checker="fixture-checker", idempotency_prefix="qyh-second-install",
    )
    with runtime.connect_factory() as conn:
        with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_AMBIGUOUS"):
            read_growth(runtime, conn)


def test_original_revoke_invalidates_publication_and_installation(installed):
    runtime, _, _ = installed
    bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
    runtime.registry_service.revoke(
        publisher="aos", bundle_id=bundle.manifest.metadata.id,
        version=bundle.manifest.metadata.version, actor="fixture-publisher",
        roles={"asset-publisher"}, publisher_scopes={"aos"},
        reason="isolated source invalidation test",
    )
    with pytest.raises(VerificationFailedError, match="current publication snapshot"):
        runtime.registry_service.get_published_reference_material(
            publisher="aos", bundle_id=bundle.manifest.metadata.id,
            version=bundle.manifest.metadata.version,
        )
    with runtime.connect_factory() as conn:
        with pytest.raises(RegistrySnapshotStaleError, match="selected release no longer available"):
            read_growth(runtime, conn)


def test_original_installation_and_publication_share_caller_transaction(installed):
    runtime, active, schema = installed
    bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
    with psycopg.connect(os.environ["AOS_DATABASE_URL"], row_factory=dict_row) as conn:
        conn.isolation_level = IsolationLevel.SERIALIZABLE
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        before = conn.execute("SELECT txid_current() AS id").fetchone()["id"]

        @contextmanager
        def borrowed():
            yield conn

        service = RegistryService(
            store=PostgresRegistryStore(borrowed), loader=runtime.prepared.loader,
            clock=lambda: conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"],
            trust_roots=runtime.prepared.trust_roots,
        )
        material = service.get_published_reference_material(
            publisher="aos", bundle_id=bundle.manifest.metadata.id,
            version=bundle.manifest.metadata.version,
        )
        view = _read_unique_active_in_transaction(
            conn, scope=TenantScope("org-org", "dev-project"), publisher="aos",
            bundle_id=bundle.manifest.metadata.id, version=bundle.manifest.metadata.version,
            content_hash=bundle.content_hash,
            release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots),
            loader=runtime.prepared.loader,
        )
        selected = next(item for item in view.releases if item.bundle_id == bundle.manifest.metadata.id)
        assert view.installation_id == str(active.installation_id)
        assert view.scope == ("org-org", "dev-project")
        assert view.current_revision == view.active_revision == 5
        assert view.authorization == "EVIDENCE_ONLY_NO_START"
        assert material["signatureFingerprint"] == selected.signature_fingerprint
        assert material["releaseEvidenceRevision"] == selected.release_evidence_revision
        assert material["contentHash"] == selected.content_hash == bundle.content_hash
        assert material["publicationSequence"] == 2
        assert conn.info.transaction_status == TransactionStatus.INTRANS
        assert conn.execute("SELECT txid_current() AS id").fetchone()["id"] == before
        conn.rollback()
    # A cross-tenant lookup cannot inherit that installation, even on fixture admin.
    with runtime.connect_factory() as conn:
        with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_MISSING"):
            _read_unique_active_in_transaction(
                conn, scope=TenantScope("dev-org", "dev-project"), publisher="aos",
                bundle_id=bundle.manifest.metadata.id, version=bundle.manifest.metadata.version,
                content_hash=bundle.content_hash,
                release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots),
                loader=runtime.prepared.loader,
            )
