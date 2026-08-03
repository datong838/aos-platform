"""Real PostgreSQL tests for immutable composition persistence."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from types import ModuleType
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from psycopg import errors, sql

from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    RegistrySnapshot,
)
from aos_api.asset_registry.composition_store import (
    CompositionPersistenceError,
    PostgresCompositionStore,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    LockIntegrityCorruptError,
    LockIntegrityInvalidError,
    RegistrySnapshotStaleError,
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
ORG = "org-store"
PROJECT = "project-store"
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
        module = _load_migration(path, f"composition_store_migration_{index}")
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
    schema = f"composition_store_{uuid.uuid4().hex}"
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
def composition_scope():
    with _isolated_schema() as scoped_connect:
        yield PostgresCompositionStore(scoped_connect), scoped_connect


def _request() -> CompositionRequest:
    return CompositionRequest.model_validate(
        {
            "requested": [
                {
                    "publisher": "aos",
                    "id": "solution.example",
                    "version": "^1.0.0",
                }
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": None,
            "currentInstallationRef": None,
        }
    )


def _empty_permission_set() -> dict:
    return {"roles": [], "markings": [], "dataScopes": [], "actionTypes": []}


def _payload(
    request: CompositionRequest,
    snapshot: RegistrySnapshot,
) -> CompositionLockPayload:
    empty_permissions = _empty_permission_set()
    return CompositionLockPayload.model_validate(
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


def _inputs() -> tuple[CompositionRequest, RegistrySnapshot, CompositionLockPayload]:
    request = _request()
    snapshot = RegistrySnapshot.build(candidates=[], checked_at=datetime.now(UTC))
    return request, snapshot, _payload(request, snapshot)


def _different_payload(payload: CompositionLockPayload) -> CompositionLockPayload:
    changed = payload.model_dump(mode="python", by_alias=True, exclude_none=False)
    changed["resolved"][0]["contentHash"] = "sha256:" + "d" * 64
    return CompositionLockPayload.model_validate(changed)


def test_create_and_get_recompute_all_persisted_hashes(composition_scope) -> None:
    store, scoped_connect = composition_scope
    request, snapshot, payload = _inputs()

    stored = store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:test",
    )
    loaded = store.get_lock(
        org_id=ORG,
        project_id=PROJECT,
        composition_id=stored.composition_id,
    )

    assert loaded == stored
    assert stored.revision == 1
    assert stored.payload == payload
    assert stored.created_at.utcoffset() is not None
    with scoped_connect() as conn:
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM bundle_composition) AS compositions,
              (SELECT COUNT(*) FROM bundle_composition_lock) AS locks
            """
        ).fetchone()
    assert counts == {"compositions": 1, "locks": 1}


def test_equivalent_input_sequentially_replays_only_the_same_payload(
    composition_scope,
) -> None:
    store, _ = composition_scope
    request, snapshot, payload = _inputs()
    first = store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:first",
    )
    replay = store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:replay",
    )

    assert replay == first
    with pytest.raises(LockIntegrityInvalidError):
        store.create_or_get(
            org_id=ORG,
            project_id=PROJECT,
            request=request,
            snapshot=snapshot,
            payload=_different_payload(payload),
            created_by="resolver:drifted",
        )


def test_equivalent_inputs_are_concurrently_idempotent(composition_scope) -> None:
    store, scoped_connect = composition_scope
    request, snapshot, payload = _inputs()
    barrier = Barrier(2)

    def persist():
        barrier.wait(timeout=5)
        return store.create_or_get(
            org_id=ORG,
            project_id=PROJECT,
            request=request,
            snapshot=snapshot,
            payload=payload,
            created_by="resolver:test",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: persist(), range(2)))

    assert first == second
    with scoped_connect() as conn:
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM bundle_composition) AS compositions,
              (SELECT COUNT(*) FROM bundle_composition_lock) AS locks
            """
        ).fetchone()
    assert counts == {"compositions": 1, "locks": 1}


def test_concurrent_equivalent_inputs_reject_different_payloads(
    composition_scope,
) -> None:
    store, scoped_connect = composition_scope
    request, snapshot, payload = _inputs()
    drifted = _different_payload(payload)
    barrier = Barrier(2)

    def persist(candidate: CompositionLockPayload):
        barrier.wait(timeout=5)
        try:
            return store.create_or_get(
                org_id=ORG,
                project_id=PROJECT,
                request=request,
                snapshot=snapshot,
                payload=candidate,
                created_by="resolver:test",
            )
        except LockIntegrityInvalidError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(persist, (payload, drifted)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, LockIntegrityInvalidError) for result in results) == 1
    with scoped_connect() as conn:
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM bundle_composition) AS compositions,
              (SELECT COUNT(*) FROM bundle_composition_lock) AS locks
            """
        ).fetchone()
    assert counts == {"compositions": 1, "locks": 1}


def test_equivalence_and_lookup_are_tenant_scoped(composition_scope) -> None:
    store, _ = composition_scope
    request, snapshot, payload = _inputs()
    first = store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:test",
    )
    second = store.create_or_get(
        org_id="org-other",
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:test",
    )

    assert first.composition_id != second.composition_id
    with pytest.raises(AssetNotFoundError):
        store.get_lock(
            org_id="org-other",
            project_id=PROJECT,
            composition_id=first.composition_id,
        )


def test_payload_mismatch_and_database_failure_leave_no_partial_rows(
    composition_scope,
) -> None:
    store, scoped_connect = composition_scope
    request, snapshot, payload = _inputs()
    other_snapshot = RegistrySnapshot.build(candidates=[], checked_at=datetime.now(UTC))
    assert other_snapshot.snapshot_hash == snapshot.snapshot_hash
    forged = payload.model_copy(update={"registry_snapshot_hash": "sha256:" + "f" * 64})
    with pytest.raises(LockIntegrityInvalidError):
        store.create_or_get(
            org_id=ORG,
            project_id=PROJECT,
            request=request,
            snapshot=other_snapshot,
            payload=forged,
            created_by="resolver:test",
        )
    stale_request = request.model_copy(
        update={"registry_snapshot_hash": "sha256:" + "f" * 64}
    )
    with pytest.raises(RegistrySnapshotStaleError):
        store.create_or_get(
            org_id=ORG,
            project_id=PROJECT,
            request=stale_request,
            snapshot=snapshot,
            payload=payload,
            created_by="resolver:test",
        )
    with pytest.raises(LockIntegrityInvalidError):
        store.create_or_get(
            org_id=ORG,
            project_id=PROJECT,
            request=request,
            snapshot=snapshot,
            payload=payload,
            created_by="x" * 241,
        )

    with scoped_connect() as conn:
        assert (
            conn.execute("SELECT COUNT(*) AS count FROM bundle_composition").fetchone()[
                "count"
            ]
            == 0
        )


@pytest.mark.parametrize(
    "hash_column",
    [
        "lock_hash",
        "permission_diff_hash",
        "migration_plan_hash",
        "contribution_diff_hash",
    ],
)
def test_every_lock_hash_is_reverified_after_direct_tamper(
    composition_scope,
    hash_column: str,
) -> None:
    store, scoped_connect = composition_scope
    request, snapshot, payload = _inputs()
    stored = store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:test",
    )

    with scoped_connect() as conn:
        savepoint = sql.Identifier(f"tamper_{uuid.uuid4().hex}")
        conn.execute(sql.SQL("SAVEPOINT {}").format(savepoint))
        with pytest.raises(errors.CheckViolation):
            conn.execute(
                sql.SQL("UPDATE bundle_composition_lock SET {} = %s").format(
                    sql.Identifier(hash_column)
                ),
                ("sha256:" + "f" * 64,),
            )
        conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(savepoint))
        conn.execute(sql.SQL("RELEASE SAVEPOINT {}").format(savepoint))
        conn.execute(
            """
            ALTER TABLE bundle_composition_lock
            DISABLE TRIGGER trg_bundle_composition_lock_immutable
            """
        )
        conn.execute(
            sql.SQL("UPDATE bundle_composition_lock SET {} = %s").format(
                sql.Identifier(hash_column)
            ),
            ("sha256:" + "f" * 64,),
        )
        conn.execute(
            """
            ALTER TABLE bundle_composition_lock
            ENABLE TRIGGER trg_bundle_composition_lock_immutable
            """
        )
        conn.commit()

    with pytest.raises(LockIntegrityCorruptError) as captured:
        store.get_lock(
            org_id=ORG,
            project_id=PROJECT,
            composition_id=stored.composition_id,
        )
    assert captured.value.details is None
    assert "payload" not in str(captured.value).lower()


def test_psycopg_failure_is_redacted() -> None:
    def unavailable():
        raise psycopg.OperationalError(
            "postgresql://private-user:private-password@internal/database"
        )

    store = PostgresCompositionStore(unavailable)
    with pytest.raises(CompositionPersistenceError) as captured:
        store.get_lock(
            org_id=ORG,
            project_id=PROJECT,
            composition_id="11111111-1111-4111-8111-111111111111",
        )
    assert str(captured.value) == "composition persistence failed"
    assert "private" not in str(captured.value)
