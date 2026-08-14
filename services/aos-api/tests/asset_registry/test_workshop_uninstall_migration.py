"""Upgrade and fail-closed downgrade proof for W1-E uninstall authority."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import psycopg
import pytest

from aos_api.asset_registry.composition_contracts import (
    RollbackInstallationRequest,
    StoredCompositionLock,
    UninstallInstallationRequest,
)
from aos_api.asset_registry.installation_store import InstallationPersistenceError
from tests.asset_registry.m5_control_support import m5_control_runtime
from tests.asset_registry.test_ecommerce_workshop_installation_projection import (
    _request,
    _response,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    API_ROOT / "alembic/versions/w1e_001_bundle_installation_uninstall.py"
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "workshop_uninstall_migration", MIGRATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Workshop uninstall migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _active(runtime, *, suffix: str):
    lock = StoredCompositionLock.model_validate_json(
        json.dumps(
            runtime.resolve(
                _request(runtime.snapshot_reader.read()),
                actor=f"maker:workshop-downgrade-{suffix}",
                idempotency_key=f"workshop-downgrade-resolve-{suffix}",
            ).response_json
        )
    )
    active = _response(
        runtime.install_to_active(
            lock=lock,
            overlay_revision="sha256:" + suffix * 64,
            maker=f"maker:workshop-downgrade-{suffix}",
            checker=f"checker:workshop-downgrade-{suffix}",
            idempotency_prefix=f"workshop-downgrade-install-{suffix}",
        )[-1]
    )
    return active


def test_uninstall_migration_is_linear_and_minimal() -> None:
    migration = _migration()
    upgrade_statements: list[str] = []
    downgrade_statements: list[str] = []

    with patch.object(migration.op, "execute", upgrade_statements.append):
        migration.upgrade()
    with patch.object(migration.op, "execute", downgrade_statements.append):
        migration.downgrade()

    assert migration.revision == "w1e_001"
    assert migration.down_revision == "w2_003"
    assert len(upgrade_statements) == 4
    assert "CREATE OR REPLACE FUNCTION" in "\n".join(upgrade_statements)
    assert "CREATE TABLE" not in "\n".join(upgrade_statements).upper()
    assert "CREATE TRIGGER" not in "\n".join(upgrade_statements).upper()
    assert "cannot downgrade w1e_001" in downgrade_statements[0]
    assert "ERRCODE = '55000'" in downgrade_statements[0]


def test_safe_downgrade_preserves_rollback_and_rejects_uninstall(tmp_path: Path) -> None:
    migration = _migration()
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        with runtime.connect_factory() as connection:
            with patch.object(migration.op, "execute", connection.execute):
                migration.downgrade()
            connection.commit()

        rollback_target = _active(runtime, suffix="6")
        rolled_back = _response(
            runtime.installation_service.rollback(
                installation_id=rollback_target.installation_id,
                request=RollbackInstallationRequest.model_validate(
                    {"reason": "Rollback remains valid after safe downgrade"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-downgrade-6",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-downgrade-rollback-6",
                if_match='"5"',
            )
        )
        assert rolled_back.state == "rolled_back"

        uninstall_target = _active(runtime, suffix="7")
        with pytest.raises(InstallationPersistenceError):
            runtime.installation_service.uninstall(
                installation_id=uninstall_target.installation_id,
                request=UninstallInstallationRequest.model_validate(
                    {"reason": "Uninstall must fail after safe downgrade"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-downgrade-7",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-downgrade-uninstall-7",
                if_match='"5"',
            )


def test_downgrade_fails_closed_when_uninstalled_history_exists(tmp_path: Path) -> None:
    migration = _migration()
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        active = _active(runtime, suffix="8")
        uninstalled = _response(
            runtime.installation_service.uninstall(
                installation_id=active.installation_id,
                request=UninstallInstallationRequest.model_validate(
                    {"reason": "Create immutable uninstall downgrade guard evidence"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-downgrade-8",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-downgrade-uninstall-8",
                if_match='"5"',
            )
        )
        assert uninstalled.state == "uninstalled"

        with runtime.connect_factory() as connection:
            with (
                patch.object(migration.op, "execute", connection.execute),
                pytest.raises(
                    psycopg.errors.ObjectNotInPrerequisiteState,
                    match="cannot downgrade w1e_001",
                ),
            ):
                migration.downgrade()
            connection.rollback()
