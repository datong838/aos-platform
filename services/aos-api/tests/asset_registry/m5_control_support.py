"""Shared real-control-plane runtime for M5 composition and installation tests."""

from __future__ import annotations

import importlib.util
import json
import uuid
from collections.abc import Callable, Collection, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from psycopg import sql

from aos_api.asset_registry.composition_contracts import (
    ApproveInstallationRequest,
    CompositionRequest,
    CreateInstallationRequest,
    EmptyInstallationActionRequest,
    InstallationResponse,
    StoredCompositionLock,
)
from aos_api.asset_registry.composition_service import CompositionService
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import (
    CommandReceipt,
    PostgresInstallationStore,
)
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.db import connect
from tests.asset_registry.m5_bundle_support import (
    M5_BUNDLE_FIXTURES,
    RuntimeSignedM5BundleSet,
    copy_and_sign_m5_bundles,
)

API_ROOT = Path(__file__).resolve().parents[2]
M5_CONTROL_MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
    API_ROOT / "alembic/versions/228asset1_composition_installation.py",
    API_ROOT / "alembic/versions/w1e_001_bundle_installation_uninstall.py",
)
M5_ORG_ID = "org-m5-synthetic"
M5_PROJECT_ID = "project-m5-synthetic"

ConnectFactory = Callable[[], AbstractContextManager[Any]]


@dataclass(frozen=True, slots=True)
class M5ControlRuntime:
    """Public test runtime backed only by production services and stores."""

    connect_factory: ConnectFactory
    org_id: str
    project_id: str
    prepared: RuntimeSignedM5BundleSet
    registry_service: RegistryService
    registry_store: PostgresRegistryStore
    snapshot_reader: RegistrySnapshotReader
    composition_store: PostgresCompositionStore
    installation_store: PostgresInstallationStore
    composition_service: CompositionService
    installation_service: InstallationService

    def database_clock(self) -> datetime:
        return _database_clock(self.connect_factory)

    def resolve(
        self,
        request: CompositionRequest,
        *,
        actor: str,
        idempotency_key: str,
        roles: Collection[str] = ("asset-installer",),
        markings: Collection[str] = (),
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> CommandReceipt:
        return self.composition_service.resolve(
            request=request,
            org_id=self.org_id if org_id is None else org_id,
            project_id=self.project_id if project_id is None else project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
        )

    def install_to_active(
        self,
        *,
        lock: StoredCompositionLock,
        overlay_revision: str,
        maker: str,
        checker: str,
        idempotency_prefix: str,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[CommandReceipt, ...]:
        """Create through active so negative tests can start from a real baseline."""

        target_org = self.org_id if org_id is None else org_id
        target_project = self.project_id if project_id is None else project_id
        created = self.installation_service.create(
            request=CreateInstallationRequest.model_validate(
                {
                    "compositionId": lock.composition_id,
                    "lockRevision": lock.revision,
                    "overlayRevision": overlay_revision,
                    "displayName": "Synthetic M5 ecommerce composition",
                }
            ),
            org_id=target_org,
            project_id=target_project,
            actor=maker,
            roles={"asset-installer"},
            markings=set(),
            idempotency_key=f"{idempotency_prefix}-create",
        )
        installation_id = InstallationResponse.model_validate_json(
            json.dumps(created.response_json)
        ).installation_id
        submitted = self.installation_service.submit(
            installation_id=installation_id,
            request=EmptyInstallationActionRequest(),
            org_id=target_org,
            project_id=target_project,
            actor=maker,
            roles={"asset-installer"},
            markings=set(),
            idempotency_key=f"{idempotency_prefix}-submit",
            if_match='"1"',
        )
        approved = self.installation_service.approve(
            installation_id=installation_id,
            request=ApproveInstallationRequest.model_validate(
                {
                    "lockHash": lock.lock_hash,
                    "permissionDiffHash": lock.permission_diff_hash,
                    "migrationPlanHash": lock.migration_plan_hash,
                    "contributionDiffHash": lock.contribution_diff_hash,
                }
            ),
            org_id=target_org,
            project_id=target_project,
            actor=checker,
            roles={"asset-install-approver"},
            markings=set(),
            idempotency_key=f"{idempotency_prefix}-approve",
            if_match='"2"',
        )
        applied = self.installation_service.apply(
            installation_id=installation_id,
            request=EmptyInstallationActionRequest(),
            org_id=target_org,
            project_id=target_project,
            actor=maker,
            roles={"asset-installer"},
            markings=set(),
            idempotency_key=f"{idempotency_prefix}-apply",
            if_match='"3"',
        )
        active = self.installation_service.verify(
            installation_id=installation_id,
            request=EmptyInstallationActionRequest(),
            org_id=target_org,
            project_id=target_project,
            actor=maker,
            roles={"asset-installer"},
            markings=set(),
            idempotency_key=f"{idempotency_prefix}-verify",
            if_match='"4"',
        )
        return created, submitted, approved, applied, active


def _load_migration(path: Path, index: int) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"m5_control_migration_{index}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load M5 migration: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements() -> list[str]:
    statements: list[str] = []
    for index, path in enumerate(M5_CONTROL_MIGRATIONS):
        module = _load_migration(path, index)
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value = []
        with (
            patch.object(module.op, "execute", statements.append),
            patch.object(module.op, "get_bind", return_value=connection),
        ):
            module.upgrade()
    return statements


def _database_clock(connect_factory: ConnectFactory) -> datetime:
    with connect_factory() as connection:
        row = connection.execute("SELECT clock_timestamp() AS checked_at").fetchone()
    if row is None or not isinstance(row["checked_at"], datetime):
        raise RuntimeError("M5 PostgreSQL clock is unavailable")
    checked_at = row["checked_at"]
    if checked_at.utcoffset() is None:
        raise RuntimeError("M5 PostgreSQL clock is timezone-naive")
    return checked_at


def _publish_four_bundles(
    *,
    store: PostgresRegistryStore,
    prepared: RuntimeSignedM5BundleSet,
    connect_factory: ConnectFactory,
) -> RegistryService:
    service = RegistryService(
        store=store,
        loader=prepared.loader,
        clock=lambda: _database_clock(connect_factory),
        trust_roots=prepared.trust_roots,
    )
    for fixture in M5_BUNDLE_FIXTURES:
        manifest = prepared.by_id(fixture.bundle_id).signed.manifest
        service.create_bundle(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            kind=manifest.kind,
            display_name=manifest.metadata.display_name,
            actor="m5-author",
            roles={"developer"},
            publisher_scopes={"aos"},
        )
        service.create_version(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            source_ref=fixture.source_ref,
            actor="m5-author",
            roles={"developer"},
            publisher_scopes={"aos"},
        )
        service.validate(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            version=manifest.metadata.version,
            actor="m5-validator",
            roles={"developer"},
            publisher_scopes={"aos"},
        )
        service.publish(
            publisher="aos",
            bundle_id=fixture.bundle_id,
            version=manifest.metadata.version,
            actor="m5-publisher",
            roles={"asset-publisher"},
            publisher_scopes={"aos"},
        )
    return service


@contextmanager
def m5_control_runtime(destination: Path) -> Iterator[M5ControlRuntime]:
    """Yield an isolated M5 control plane and always clean it up."""

    schema = f"m5_control_{uuid.uuid4().hex}"
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
        signed_at = _database_clock(scoped_connect)
        prepared = copy_and_sign_m5_bundles(destination, signed_at=signed_at)
        registry_store = PostgresRegistryStore(scoped_connect)
        registry_service = _publish_four_bundles(
            store=registry_store,
            prepared=prepared,
            connect_factory=scoped_connect,
        )
        release_policy = ReleasePolicy(trust_roots=prepared.trust_roots)
        snapshot_reader = RegistrySnapshotReader(
            connect_factory=scoped_connect,
            release_policy=release_policy,
        )
        composition_store = PostgresCompositionStore(scoped_connect)
        installation_store = PostgresInstallationStore(scoped_connect)
        composition_service = CompositionService(
            snapshot_reader=snapshot_reader,
            composition_store=composition_store,
            command_store=installation_store,
            baseline_reader=installation_store,
        )
        installation_service = InstallationService(
            store=installation_store,
            composition_store=composition_store,
            revalidator=InstallationRevalidator(release_policy=release_policy),
        )
        yield M5ControlRuntime(
            connect_factory=scoped_connect,
            org_id=M5_ORG_ID,
            project_id=M5_PROJECT_ID,
            prepared=prepared,
            registry_service=registry_service,
            registry_store=registry_store,
            snapshot_reader=snapshot_reader,
            composition_store=composition_store,
            installation_store=installation_store,
            composition_service=composition_service,
            installation_service=installation_service,
        )
    finally:
        if created:
            with connect() as cleanup:
                cleanup.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
                cleanup.commit()
