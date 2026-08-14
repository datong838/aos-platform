"""Real PostgreSQL proof for Workshop projection over existing installation semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionRequest,
    CreateInstallationRequest,
    InstallationResponse,
    RollbackInstallationRequest,
    StoredCompositionLock,
)
from aos_api.ecommerce_workshop_catalog import (
    EcommerceWorkshopCatalog,
    PostgresWorkshopCatalogSource,
)
from aos_api.asset_registry.errors import (
    CurrentInstallationStaleError,
    InstallationStateConflictError,
)
from tests.asset_registry.m5_control_support import m5_control_runtime
from tests.asset_registry.test_m5_ecommerce_composition import LEAF_IDS

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY_FIXTURE = (
    REPO_ROOT
    / "services/aos-api/tests/asset_registry/fixtures/m5/instance-overlay.synthetic.json"
)


def _request(
    snapshot,
    *,
    current_installation_ref=None,
    environment: str = "dev",
) -> CompositionRequest:
    versions = {item.id: item.version for item in snapshot.candidates}
    return CompositionRequest.model_validate(
        {
            "requested": [
                {
                    "publisher": "aos",
                    "id": bundle_id,
                    "version": versions[bundle_id],
                }
                for bundle_id in LEAF_IDS
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": environment,
            "registrySnapshotHash": snapshot.snapshot_hash,
            "currentInstallationRef": current_installation_ref,
        }
    )


def _response(receipt) -> InstallationResponse:
    return InstallationResponse.model_validate_json(json.dumps(receipt.response_json))


def _catalog(runtime) -> EcommerceWorkshopCatalog:
    return EcommerceWorkshopCatalog(
        source=PostgresWorkshopCatalogSource(runtime.connect_factory),
        loader=runtime.prepared.loader,
        clock=runtime.database_clock,
    )


def test_active_exact_lock_projects_eight_modules_and_rollback_preserves_history(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        resolved = runtime.resolve(
            _request(runtime.snapshot_reader.read()),
            actor="maker:workshop-projection",
            idempotency_key="workshop-projection-resolve",
        )
        lock = StoredCompositionLock.model_validate_json(
            json.dumps(resolved.response_json)
        )
        overlay_revision = canonical_sha256(
            json.loads(OVERLAY_FIXTURE.read_text(encoding="utf-8"))
        )
        receipts = runtime.install_to_active(
            lock=lock,
            overlay_revision=overlay_revision,
            maker="maker:workshop-projection",
            checker="checker:workshop-projection",
            idempotency_prefix="workshop-projection-install",
        )
        active = _response(receipts[-1])
        assert active.state == "active"
        assert active.active_revision == 5
        assert active.previous_active_revision is None

        catalog = _catalog(runtime)
        projected = catalog.list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        assert projected.count == 8
        assert {item.module_id for item in projected.items} == {
            "ecommerce.task-cockpit",
            "ecommerce.content-campaign",
            "ecommerce.operations",
            "ecommerce.creator-growth",
            "ecommerce.media-studio",
            "ecommerce.analyst",
            "ecommerce.price-governance",
            "ecommerce.customer",
        }
        assert all(
            item.installation_ref.installation_id == active.installation_id
            and item.installation_ref.revision == active.active_revision
            and item.installation_ref.lock_hash == lock.lock_hash
            for item in projected.items
        )

        canary = catalog.list_modules(
            org_id="dev-org",
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        assert canary.count == 0

        rolled = _response(
            runtime.installation_service.rollback(
                installation_id=active.installation_id,
                request=RollbackInstallationRequest.model_validate(
                    {"reason": "Workshop projection rollback proof"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-projection",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-projection-rollback",
                if_match='"5"',
            )
        )
        assert rolled.state == "rolled_back"
        assert rolled.active_revision is None
        assert rolled.previous_active_revision is None
        assert catalog.list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        ).count == 0

        with runtime.connect_factory() as connection:
            history = connection.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM bundle_installation_revision
                    WHERE org_id=%s AND project_id=%s) AS revisions,
                  (SELECT COUNT(*) FROM bundle_installation_event
                    WHERE org_id=%s AND project_id=%s) AS events,
                  (SELECT COUNT(*) FROM bundle_composition_lock
                    WHERE org_id=%s AND project_id=%s) AS locks
                """,
                (
                    runtime.org_id,
                    runtime.project_id,
                    runtime.org_id,
                    runtime.project_id,
                    runtime.org_id,
                    runtime.project_id,
                ),
            ).fetchone()
        assert history == {"revisions": 6, "events": 6, "locks": 1}


def test_replacement_leaf_shadows_predecessor_and_rollback_restores_it(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        first_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot),
                    actor="maker:workshop-replacement",
                    idempotency_key="workshop-replacement-resolve-a",
                ).response_json
            )
        )
        first_overlay = "sha256:" + "a" * 64
        first = _response(
            runtime.install_to_active(
                lock=first_lock,
                overlay_revision=first_overlay,
                maker="maker:workshop-replacement",
                checker="checker:workshop-replacement",
                idempotency_prefix="workshop-replacement-install-a",
            )[-1]
        )

        second_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(
                        snapshot,
                        current_installation_ref={
                            "installationId": first.installation_id,
                            "revision": first.active_revision,
                            "lockHash": first_lock.lock_hash,
                            "overlayRevision": first_overlay,
                        },
                    ),
                    actor="maker:workshop-replacement",
                    idempotency_key="workshop-replacement-resolve-b",
                ).response_json
            )
        )
        assert second_lock.payload.current_installation_ref is not None
        second_overlay = "sha256:" + "b" * 64
        second = _response(
            runtime.install_to_active(
                lock=second_lock,
                overlay_revision=second_overlay,
                maker="maker:workshop-replacement",
                checker="checker:workshop-replacement",
                idempotency_prefix="workshop-replacement-install-b",
            )[-1]
        )

        third_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(
                        snapshot,
                        current_installation_ref={
                            "installationId": second.installation_id,
                            "revision": second.active_revision,
                            "lockHash": second_lock.lock_hash,
                            "overlayRevision": second_overlay,
                        },
                    ),
                    actor="maker:workshop-replacement",
                    idempotency_key="workshop-replacement-resolve-c",
                ).response_json
            )
        )
        third = _response(
            runtime.install_to_active(
                lock=third_lock,
                overlay_revision="sha256:" + "f" * 64,
                maker="maker:workshop-replacement",
                checker="checker:workshop-replacement",
                idempotency_prefix="workshop-replacement-install-c",
            )[-1]
        )

        catalog = _catalog(runtime)
        replacement = catalog.list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        assert replacement.count == 8
        assert {
            item.installation_ref.installation_id for item in replacement.items
        } == {third.installation_id}

        third_rolled = _response(
            runtime.installation_service.rollback(
                installation_id=third.installation_id,
                request=RollbackInstallationRequest.model_validate(
                    {"reason": "Restore middle Workshop predecessor"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-replacement",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-replacement-rollback-c",
                if_match='"5"',
            )
        )
        assert third_rolled.state == "rolled_back"
        middle = catalog.list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        assert {item.installation_ref.installation_id for item in middle.items} == {
            second.installation_id
        }

        rolled = _response(
            runtime.installation_service.rollback(
                installation_id=second.installation_id,
                request=RollbackInstallationRequest.model_validate(
                    {"reason": "Restore exact Workshop predecessor"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-replacement",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-replacement-rollback-b",
                if_match='"5"',
            )
        )
        assert rolled.state == "rolled_back"
        restored = catalog.list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        assert restored.count == 8
        assert {item.installation_ref.installation_id for item in restored.items} == {
            first.installation_id
        }

        with runtime.connect_factory() as connection:
            history = connection.execute(
                """
                SELECT installation_id, current_revision, active_revision,
                       previous_active_revision
                  FROM bundle_installation
                 WHERE org_id=%s AND project_id=%s
                 ORDER BY installation_id
                """,
                (runtime.org_id, runtime.project_id),
            ).fetchall()
        assert len(history) == 3
        by_id = {str(row["installation_id"]): dict(row) for row in history}
        assert by_id[first.installation_id]["active_revision"] == 5
        assert by_id[first.installation_id]["current_revision"] == 5
        assert by_id[second.installation_id]["active_revision"] is None
        assert by_id[second.installation_id]["current_revision"] == 6
        assert by_id[third.installation_id]["active_revision"] is None
        assert by_id[third.installation_id]["current_revision"] == 6


def test_active_replacement_blocks_predecessor_rollback_and_sibling_activation(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        root_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot),
                    actor="maker:workshop-branch",
                    idempotency_key="workshop-branch-resolve-root",
                ).response_json
            )
        )
        root_overlay = "sha256:" + "c" * 64
        root = _response(
            runtime.install_to_active(
                lock=root_lock,
                overlay_revision=root_overlay,
                maker="maker:workshop-branch",
                checker="checker:workshop-branch",
                idempotency_prefix="workshop-branch-install-root",
            )[-1]
        )
        root_ref = {
            "installationId": root.installation_id,
            "revision": root.active_revision,
            "lockHash": root_lock.lock_hash,
            "overlayRevision": root_overlay,
        }

        child_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot, current_installation_ref=root_ref),
                    actor="maker:workshop-branch",
                    idempotency_key="workshop-branch-resolve-child",
                ).response_json
            )
        )
        child = _response(
            runtime.install_to_active(
                lock=child_lock,
                overlay_revision="sha256:" + "d" * 64,
                maker="maker:workshop-branch",
                checker="checker:workshop-branch",
                idempotency_prefix="workshop-branch-install-child",
            )[-1]
        )

        with pytest.raises(
            InstallationStateConflictError,
            match="active replacement",
        ):
            runtime.installation_service.rollback(
                installation_id=root.installation_id,
                request=RollbackInstallationRequest.model_validate(
                    {"reason": "Invalid predecessor rollback"}
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-branch",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-branch-rollback-root",
                if_match='"5"',
            )

        sibling_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot, current_installation_ref=root_ref),
                    actor="maker:workshop-branch",
                    idempotency_key="workshop-branch-resolve-sibling",
                ).response_json
            )
        )
        with pytest.raises(
            InstallationStateConflictError,
            match="already has an active replacement",
        ):
            runtime.install_to_active(
                lock=sibling_lock,
                overlay_revision="sha256:" + "e" * 64,
                maker="maker:workshop-branch",
                checker="checker:workshop-branch",
                idempotency_prefix="workshop-branch-install-sibling",
            )

        with runtime.connect_factory() as connection:
            sibling = connection.execute(
                """
                SELECT current_revision, active_revision
                  FROM bundle_installation
                 WHERE org_id=%s AND project_id=%s
                   AND installation_id NOT IN (%s, %s)
                """,
                (
                    runtime.org_id,
                    runtime.project_id,
                    root.installation_id,
                    child.installation_id,
                ),
            ).fetchone()
        assert sibling == {"current_revision": 4, "active_revision": None}

        projected = _catalog(runtime).list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        assert projected.count == 8
        assert {item.installation_ref.installation_id for item in projected.items} == {
            child.installation_id
        }


def test_stale_predecessor_is_rejected_again_when_replacement_draft_is_created(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        root_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot),
                    actor="maker:workshop-stale",
                    idempotency_key="workshop-stale-resolve-root",
                ).response_json
            )
        )
        root_overlay = "sha256:" + "1" * 64
        root = _response(
            runtime.install_to_active(
                lock=root_lock,
                overlay_revision=root_overlay,
                maker="maker:workshop-stale",
                checker="checker:workshop-stale",
                idempotency_prefix="workshop-stale-install-root",
            )[-1]
        )
        replacement_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(
                        snapshot,
                        current_installation_ref={
                            "installationId": root.installation_id,
                            "revision": root.active_revision,
                            "lockHash": root_lock.lock_hash,
                            "overlayRevision": root_overlay,
                        },
                    ),
                    actor="maker:workshop-stale",
                    idempotency_key="workshop-stale-resolve-replacement",
                ).response_json
            )
        )
        runtime.installation_service.rollback(
            installation_id=root.installation_id,
            request=RollbackInstallationRequest.model_validate(
                {"reason": "Make resolved predecessor stale"}
            ),
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            actor="maker:workshop-stale",
            roles={"asset-installer"},
            markings=set(),
            idempotency_key="workshop-stale-rollback-root",
            if_match='"5"',
        )

        with pytest.raises(CurrentInstallationStaleError):
            runtime.installation_service.create(
                request=CreateInstallationRequest.model_validate(
                    {
                        "compositionId": replacement_lock.composition_id,
                        "lockRevision": replacement_lock.revision,
                        "overlayRevision": "sha256:" + "2" * 64,
                        "displayName": "Stale Workshop replacement",
                    }
                ),
                org_id=runtime.org_id,
                project_id=runtime.project_id,
                actor="maker:workshop-stale",
                roles={"asset-installer"},
                markings=set(),
                idempotency_key="workshop-stale-create-replacement",
            )
        with runtime.connect_factory() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) AS count
                  FROM bundle_installation
                 WHERE org_id=%s AND project_id=%s
                """,
                (runtime.org_id, runtime.project_id),
            ).fetchone()
        assert count == {"count": 1}


def test_two_tenants_project_their_own_exact_locks_and_canary_stays_empty(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        primary_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot),
                    actor="maker:workshop-tenant-primary",
                    idempotency_key="workshop-tenant-primary-resolve",
                ).response_json
            )
        )
        primary = _response(
            runtime.install_to_active(
                lock=primary_lock,
                overlay_revision="sha256:" + "3" * 64,
                maker="maker:workshop-tenant-primary",
                checker="checker:workshop-tenant-primary",
                idempotency_prefix="workshop-tenant-primary-install",
            )[-1]
        )

        secondary_org = "org-m5-secondary"
        secondary_project = "project-m5-secondary"
        secondary_lock = StoredCompositionLock.model_validate_json(
            json.dumps(
                runtime.resolve(
                    _request(snapshot, environment="staging"),
                    actor="maker:workshop-tenant-secondary",
                    idempotency_key="workshop-tenant-secondary-resolve",
                    org_id=secondary_org,
                    project_id=secondary_project,
                ).response_json
            )
        )
        secondary = _response(
            runtime.install_to_active(
                lock=secondary_lock,
                overlay_revision="sha256:" + "4" * 64,
                maker="maker:workshop-tenant-secondary",
                checker="checker:workshop-tenant-secondary",
                idempotency_prefix="workshop-tenant-secondary-install",
                org_id=secondary_org,
                project_id=secondary_project,
            )[-1]
        )
        assert primary_lock.lock_hash != secondary_lock.lock_hash

        catalog = _catalog(runtime)
        primary_modules = catalog.list_modules(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            roles=["operator"],
            markings=["public"],
        )
        secondary_modules = catalog.list_modules(
            org_id=secondary_org,
            project_id=secondary_project,
            roles=["operator"],
            markings=["public"],
        )
        canary = catalog.list_modules(
            org_id="dev-org",
            project_id="dev-project",
            roles=["operator"],
            markings=["public"],
        )
        assert primary_modules.count == secondary_modules.count == 8
        assert {item.installation_ref.installation_id for item in primary_modules.items} == {
            primary.installation_id
        }
        assert {
            item.installation_ref.installation_id for item in secondary_modules.items
        } == {secondary.installation_id}
        assert canary.count == 0
