"""Real PostgreSQL tests for draft installation and command primitives."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import ModuleType
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from psycopg import sql

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    CreateInstallationRequest,
    InstallationListQuery,
    RegistrySnapshot,
)
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    IdempotencyConflictError,
    RevisionConflictError,
)
from aos_api.asset_registry.installation_store import (
    CommandResult,
    InstallationPersistenceError,
    PostgresInstallationStore,
    command_request_hash,
)
from aos_api.db import connect

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
    API_ROOT / "alembic/versions/228asset1_composition_installation.py",
)
ORG = "org-installation"
PROJECT = "project-installation"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def _load_migration(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements() -> list[str]:
    statements: list[str] = []
    for index, path in enumerate(MIGRATIONS):
        module = _load_migration(path, f"installation_store_migration_{index}")
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value = []
        with (
            patch.object(module.op, "execute", statements.append),
            patch.object(module.op, "get_bind", return_value=connection),
        ):
            module.upgrade()
    return statements


@contextmanager
def _isolated_schema():
    schema = f"installation_store_{uuid.uuid4().hex}"
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


@pytest.fixture()
def installation_scope():
    with _isolated_schema() as scoped_connect:
        composition_store = PostgresCompositionStore(scoped_connect)
        installation_store = PostgresInstallationStore(scoped_connect)
        yield composition_store, installation_store, scoped_connect


def _composition_inputs():
    request = CompositionRequest.model_validate(
        {
            "requested": [
                {
                    "publisher": "aos",
                    "id": "solution.example",
                    "version": "1.0.0",
                }
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
        }
    )
    snapshot = RegistrySnapshot.build(candidates=[], checked_at=datetime.now(UTC))
    empty_permissions = {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    payload = CompositionLockPayload.model_validate(
        {
            "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
            "resolverVersion": "aos-resolver/1.0.0",
            "request": request.lock_request(),
            "registrySnapshotHash": snapshot.snapshot_hash,
            "resolved": [
                {
                    "publisher": "aos",
                    "id": "solution.example",
                    "version": "1.0.0",
                    "kind": "SolutionPack",
                    "contentHash": SHA_A,
                    "signatureFingerprint": SHA_B,
                    "releaseEvidenceRevision": SHA_C,
                    "dependencies": [],
                    "optionalDependencies": [],
                    "conflicts": [],
                    "capabilities": {"provides": [], "requires": []},
                    "permissions": empty_permissions,
                    "migration": {
                        "planRef": None,
                        "downgradePolicy": "retain-canonical",
                    },
                    "contributions": [],
                    "selectionReason": "requested",
                }
            ],
            "edges": [],
            "capabilityProviders": [],
            "permissionDiff": {
                "baseline": empty_permissions,
                "target": empty_permissions,
                "added": empty_permissions,
                "removed": empty_permissions,
                "unchanged": empty_permissions,
            },
            "migrationPlan": {
                "baseline": [],
                "target": [],
                "added": [],
                "removed": [],
                "changed": [],
            },
            "contributionDiff": {
                "baseline": [],
                "target": [],
                "added": [],
                "removed": [],
                "unchanged": [],
            },
            "currentInstallationRef": None,
        }
    )
    return request, snapshot, payload


def _seed_composition(store: PostgresCompositionStore):
    request, snapshot, payload = _composition_inputs()
    return store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:test",
    )


def _create_request(composition_id: str) -> CreateInstallationRequest:
    return CreateInstallationRequest.model_validate(
        {
            "compositionId": composition_id,
            "lockRevision": 1,
            "overlayRevision": "overlay-v1",
            "displayName": "Store installation",
        }
    )


def test_create_get_and_list_draft_are_tenant_scoped(installation_scope) -> None:
    composition_store, store, scoped_connect = installation_scope
    lock = _seed_composition(composition_store)
    record = store.create_draft(
        org_id=ORG,
        project_id=PROJECT,
        request=_create_request(lock.composition_id),
        requested_by="requester:test",
    )

    assert record.state == "draft"
    assert record.current_revision == record.etag_version == 1
    assert record.active_revision is None
    assert record.previous_active_revision is None
    assert record.current.lock_hash == lock.lock_hash
    assert [event.to_state for event in record.events] == ["draft"]
    assert (
        store.get_installation(
            org_id=ORG,
            project_id=PROJECT,
            installation_id=record.installation_id,
        )
        == record
    )

    listed = store.list_installations(
        org_id=ORG,
        project_id=PROJECT,
        query=InstallationListQuery.model_validate({"state": "draft"}),
    )
    assert listed.total == 1
    assert [item.installation_id for item in listed.items] == [record.installation_id]
    empty_page = store.list_installations(
        org_id=ORG,
        project_id=PROJECT,
        query=InstallationListQuery.model_validate({"offset": 1}),
    )
    assert empty_page.total == 1
    assert empty_page.items == []
    with pytest.raises(AssetNotFoundError):
        store.get_installation(
            org_id="org-other",
            project_id=PROJECT,
            installation_id=record.installation_id,
        )
    with scoped_connect() as conn:
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM bundle_installation) AS installations,
              (SELECT COUNT(*) FROM bundle_installation_revision) AS revisions,
              (SELECT COUNT(*) FROM bundle_installation_event) AS events
            """
        ).fetchone()
    assert counts == {"installations": 1, "revisions": 1, "events": 1}


def test_cross_tenant_lock_and_failed_create_leave_no_partial_installation(
    installation_scope,
) -> None:
    composition_store, store, scoped_connect = installation_scope
    lock = _seed_composition(composition_store)
    request = _create_request(lock.composition_id)

    with pytest.raises(AssetNotFoundError):
        store.create_draft(
            org_id="org-other",
            project_id=PROJECT,
            request=request,
            requested_by="requester:test",
        )
    with pytest.raises(InstallationPersistenceError):
        store.create_draft(
            org_id=ORG,
            project_id=PROJECT,
            request=request,
            requested_by="x" * 241,
        )

    with scoped_connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) AS count FROM bundle_installation"
            ).fetchone()["count"]
            == 0
        )


def test_idempotent_command_replays_before_invoking_handler_and_is_scoped(
    installation_scope,
) -> None:
    _, store, scoped_connect = installation_scope
    calls: list[str] = []
    request_hash = command_request_hash(
        subject="user:test",
        path_params={},
        body={},
        if_match=None,
    )

    def handler(conn):
        calls.append("called")
        assert conn.execute("SELECT 1 AS value").fetchone()["value"] == 1
        return CommandResult(201, {"installationId": "safe"}, '"1"')

    first = store.execute_idempotent(
        org_id=ORG,
        project_id=PROJECT,
        operation="create-installation",
        idempotency_key="same-key",
        subject="user:test",
        request_hash=request_hash,
        handler=handler,
    )
    replay = store.execute_idempotent(
        org_id=ORG,
        project_id=PROJECT,
        operation="create-installation",
        idempotency_key="same-key",
        subject="user:test",
        request_hash=request_hash,
        handler=handler,
    )

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.response_json == first.response_json
    assert calls == ["called"]
    with pytest.raises(IdempotencyConflictError):
        store.execute_idempotent(
            org_id=ORG,
            project_id=PROJECT,
            operation="create-installation",
            idempotency_key="same-key",
            subject="user:test",
            request_hash=canonical_sha256({"different": True}),
            handler=handler,
        )

    other = store.execute_idempotent(
        org_id="org-other",
        project_id=PROJECT,
        operation="create-installation",
        idempotency_key="same-key",
        subject="user:test",
        request_hash=request_hash,
        handler=handler,
    )
    assert other.replayed is False
    with scoped_connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) AS count FROM bundle_installation_command"
            ).fetchone()["count"]
            == 2
        )


def test_idempotent_failure_rolls_back_business_write_and_receipt(
    installation_scope,
) -> None:
    _, store, scoped_connect = installation_scope
    request_hash = canonical_sha256({"command": "failure"})

    def handler(conn):
        conn.execute(
            """
            INSERT INTO bundle_installation_command (
              org_id, project_id, operation, idempotency_key, subject,
              request_hash, status_code, response_json
            ) VALUES (
              'temporary', 'temporary', 'temporary', 'temporary', 'temporary',
              %s, 201, '{}'
            )
            """,
            (request_hash,),
        )
        raise RuntimeError("domain failure")

    with pytest.raises(RuntimeError, match="domain failure"):
        store.execute_idempotent(
            org_id=ORG,
            project_id=PROJECT,
            operation="create-installation",
            idempotency_key="failure-key",
            subject="user:test",
            request_hash=request_hash,
            handler=handler,
        )
    with scoped_connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) AS count FROM bundle_installation_command"
            ).fetchone()["count"]
            == 0
        )


def test_concurrent_same_command_serializes_to_one_receipt(installation_scope) -> None:
    _, store, _ = installation_scope
    request_hash = command_request_hash(
        subject="user:test",
        path_params={},
        body={"value": 1},
        if_match=None,
    )
    handler_started = Event()
    release_handler = Event()
    calls: list[str] = []

    def handler(conn):
        calls.append("called")
        assert conn.execute("SELECT 1 AS value").fetchone()["value"] == 1
        handler_started.set()
        assert release_handler.wait(timeout=5)
        return CommandResult(201, {"result": "created"})

    def execute():
        return store.execute_idempotent(
            org_id=ORG,
            project_id=PROJECT,
            operation="resolve",
            idempotency_key="concurrent-key",
            subject="user:test",
            request_hash=request_hash,
            handler=handler,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(execute)
        assert handler_started.wait(timeout=5)
        second_future = pool.submit(execute)
        release_handler.set()
        receipts = [first_future.result(timeout=5), second_future.result(timeout=5)]

    assert calls == ["called"]
    assert sorted(receipt.replayed for receipt in receipts) == [False, True]
    assert receipts[0].response_json == receipts[1].response_json


def test_command_request_hash_covers_only_the_frozen_envelope() -> None:
    first = command_request_hash(
        subject="user:test",
        path_params={"installationId": "one"},
        body={"value": 1},
        if_match='"1"',
    )
    reordered = command_request_hash(
        subject="user:test",
        path_params={"installationId": "one"},
        body={"value": 1},
        if_match='"1"',
    )
    changed_etag = command_request_hash(
        subject="user:test",
        path_params={"installationId": "one"},
        body={"value": 1},
        if_match='"2"',
    )

    assert first == reordered
    assert first != changed_etag
    assert first == canonical_sha256(
        {
            "subject": "user:test",
            "pathParams": {"installationId": "one"},
            "body": {"value": 1},
            "ifMatch": '"1"',
        }
    )


def test_draft_creation_can_share_idempotency_transaction_and_cas_lock(
    installation_scope,
) -> None:
    composition_store, store, scoped_connect = installation_scope
    lock = _seed_composition(composition_store)
    request = _create_request(lock.composition_id)
    request_hash = canonical_sha256({"create": request.model_dump(mode="json")})
    installation_ids: list[str] = []

    def handler(conn):
        record = store.create_draft_in_transaction(
            conn,
            org_id=ORG,
            project_id=PROJECT,
            request=request,
            requested_by="requester:test",
        )
        installation_ids.append(record.installation_id)
        return CommandResult(
            201,
            record.model_dump(mode="json", by_alias=True, exclude_none=False),
            '"1"',
        )

    first = store.execute_idempotent(
        org_id=ORG,
        project_id=PROJECT,
        operation="create-installation",
        idempotency_key="create-key",
        subject="requester:test",
        request_hash=request_hash,
        handler=handler,
    )
    replay = store.execute_idempotent(
        org_id=ORG,
        project_id=PROJECT,
        operation="create-installation",
        idempotency_key="create-key",
        subject="requester:test",
        request_hash=request_hash,
        handler=handler,
    )
    assert replay.replayed is True
    assert replay.response_json == first.response_json
    assert len(installation_ids) == 1

    with scoped_connect() as conn:
        locked = store.lock_for_cas(
            conn,
            org_id=ORG,
            project_id=PROJECT,
            installation_id=installation_ids[0],
            expected_etag_version=1,
        )
        assert locked.etag_version == 1
        with pytest.raises(RevisionConflictError):
            store.lock_for_cas(
                conn,
                org_id=ORG,
                project_id=PROJECT,
                installation_id=installation_ids[0],
                expected_etag_version=2,
            )
        with pytest.raises(AssetNotFoundError):
            store.lock_for_cas(
                conn,
                org_id="org-other",
                project_id=PROJECT,
                installation_id=installation_ids[0],
                expected_etag_version=1,
            )
        conn.rollback()


def test_psycopg_failure_is_redacted() -> None:
    def unavailable():
        raise psycopg.OperationalError(
            "postgresql://placeholder-user:placeholder-password@placeholder-host/database"
        )

    store = PostgresInstallationStore(unavailable)
    with pytest.raises(InstallationPersistenceError) as captured:
        store.get_installation(
            org_id=ORG,
            project_id=PROJECT,
            installation_id="22222222-2222-4222-8222-222222222222",
        )
    assert str(captured.value) == "installation persistence failed"
    assert "placeholder" not in str(captured.value)
