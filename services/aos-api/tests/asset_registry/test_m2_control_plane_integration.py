"""Real PostgreSQL concurrency checks for the integrated M2 control plane."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from psycopg import sql

from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    CreateInstallationRequest,
    RegistrySnapshot,
)
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.errors import RevisionConflictError
from aos_api.asset_registry.installation_revalidation import RevalidationResult
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.db import connect

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
    API_ROOT / "alembic/versions/228asset1_composition_installation.py",
)
ORG = "org-m2-adversarial"
PROJECT = "project-m2-adversarial"
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
        module = _load_migration(path, f"m2_integration_migration_{index}")
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value = []
        with (
            patch.object(module.op, "execute", statements.append),
            patch.object(module.op, "get_bind", return_value=connection),
        ):
            module.upgrade()
    return statements


@contextmanager
def _isolated_scope():
    schema = f"m2_integration_{uuid.uuid4().hex}"
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            for statement in _upgrade_statements():
                conn.execute(statement)
            conn.commit()
    except psycopg.Error as exc:
        pytest.skip(f"PG unavailable: {exc}")

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


def _seed_lock(store: PostgresCompositionStore):
    request = CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": "aos", "id": "solution.example", "version": "1.0.0"}
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
        }
    )
    snapshot = RegistrySnapshot.build(candidates=[], checked_at=datetime.now(UTC))
    empty = {"roles": [], "markings": [], "dataScopes": [], "actionTypes": []}
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
                    "permissions": empty,
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
                "baseline": empty,
                "target": empty,
                "added": empty,
                "removed": empty,
                "unchanged": empty,
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
    return store.create_or_get(
        org_id=ORG,
        project_id=PROJECT,
        request=request,
        snapshot=snapshot,
        payload=payload,
        created_by="resolver:test",
    )


def test_concurrent_distinct_commands_with_same_etag_advance_only_once() -> None:
    with _isolated_scope() as scoped_connect:
        composition_store = PostgresCompositionStore(scoped_connect)
        store = PostgresInstallationStore(scoped_connect)
        lock = _seed_lock(composition_store)

        class Revalidator:
            def revalidate_in_transaction(self, conn, *, lock):
                checked_at = conn.execute(
                    "SELECT clock_timestamp() AS checked_at"
                ).fetchone()["checked_at"]
                return RevalidationResult(checked_at=checked_at)

        service = InstallationService(
            store=store,
            composition_store=composition_store,
            revalidator=Revalidator(),
        )
        created = service.create(
            request=CreateInstallationRequest.model_validate(
                {
                    "compositionId": lock.composition_id,
                    "lockRevision": 1,
                    "overlayRevision": "overlay-v1",
                    "displayName": "Concurrent installation",
                }
            ),
            org_id=ORG,
            project_id=PROJECT,
            actor="requester:test",
            roles=["asset-installer"],
            markings=[],
            idempotency_key="create-concurrent",
        )
        installation_id = created.response_json["installationId"]

        def submit(key: str):
            return service.submit(
                installation_id=installation_id,
                request={},
                org_id=ORG,
                project_id=PROJECT,
                actor="requester:test",
                roles=["asset-installer"],
                markings=[],
                idempotency_key=key,
                if_match='"1"',
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit, f"submit-{index}") for index in range(2)]
            outcomes = []
            for future in futures:
                try:
                    outcomes.append(future.result(timeout=10))
                except RevisionConflictError as exc:
                    outcomes.append(exc)

        assert sum(not isinstance(item, Exception) for item in outcomes) == 1
        assert sum(isinstance(item, RevisionConflictError) for item in outcomes) == 1
        record = store.get_installation(
            org_id=ORG,
            project_id=PROJECT,
            installation_id=installation_id,
        )
        assert record.state == "submitted"
        assert record.current_revision == record.etag_version == 2
        with scoped_connect() as conn:
            counts = conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM bundle_installation_command
                    WHERE operation='bundle_installations.submit') AS receipts,
                  (SELECT COUNT(*) FROM bundle_installation_revision) AS revisions,
                  (SELECT COUNT(*) FROM bundle_installation_event) AS events
                """
            ).fetchone()
        assert counts == {"receipts": 1, "revisions": 2, "events": 2}
