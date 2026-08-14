"""Real PostgreSQL proof for Workshop projection over existing installation semantics."""

from __future__ import annotations

import json
from pathlib import Path

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionRequest,
    InstallationResponse,
    RollbackInstallationRequest,
    StoredCompositionLock,
)
from aos_api.ecommerce_workshop_catalog import (
    EcommerceWorkshopCatalog,
    PostgresWorkshopCatalogSource,
)
from tests.asset_registry.m5_control_support import m5_control_runtime
from tests.asset_registry.test_m5_ecommerce_composition import LEAF_IDS

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY_FIXTURE = (
    REPO_ROOT
    / "services/aos-api/tests/asset_registry/fixtures/m5/instance-overlay.synthetic.json"
)


def _request(snapshot) -> CompositionRequest:
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
            "environment": "dev",
            "registrySnapshotHash": snapshot.snapshot_hash,
            "currentInstallationRef": None,
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
