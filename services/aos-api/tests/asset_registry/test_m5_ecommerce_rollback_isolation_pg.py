"""M5-2 real-PG proof that a revoked release cannot block safe rollback."""

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
from aos_api.asset_registry.errors import RegistrySnapshotStaleError
from aos_api.asset_registry.installation_evidence import verify_event_evidence
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.release_policy import ReleasePolicy
from tests.asset_registry.m5_control_support import (
    M5ControlRuntime,
    m5_control_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY_FIXTURE = (
    REPO_ROOT
    / "services/aos-api/tests/asset_registry/fixtures/m5/instance-overlay.synthetic.json"
)
LEAF_IDS = (
    "platform.ecommerce.niushop",
    "solution.ecommerce.growth",
    "solution.ecommerce.operations-base",
)
REVOKED_ID = "platform.ecommerce.niushop"
MAKER = "maker:m5-w3"
CHECKER = "checker:m5-w3"


def _request(snapshot_hash: str) -> CompositionRequest:
    return CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": "aos", "id": bundle_id, "version": "1.0.0"}
                for bundle_id in LEAF_IDS
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": snapshot_hash,
            "currentInstallationRef": None,
        }
    )


def _response(receipt) -> InstallationResponse:
    return InstallationResponse.model_validate_json(json.dumps(receipt.response_json))


def _installation_snapshot(
    runtime: M5ControlRuntime, installation_id: str
) -> dict[str, object]:
    with runtime.connect_factory() as connection:
        row = connection.execute(
            """
            SELECT i.current_revision, i.active_revision,
                   i.previous_active_revision, i.etag_version,
                   (SELECT COUNT(*)
                      FROM bundle_installation_revision r
                     WHERE r.org_id = i.org_id
                       AND r.project_id = i.project_id
                       AND r.installation_pk = i.installation_pk) AS revisions,
                   (SELECT COUNT(*)
                      FROM bundle_installation_event e
                     WHERE e.org_id = i.org_id
                       AND e.project_id = i.project_id
                       AND e.installation_pk = i.installation_pk) AS events
              FROM bundle_installation i
             WHERE i.org_id = %s AND i.project_id = %s
               AND i.installation_id = %s
            """,
            (runtime.org_id, runtime.project_id, installation_id),
        ).fetchone()
    assert row is not None
    return dict(row)


def _history(
    runtime: M5ControlRuntime, installation_id: str
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with runtime.connect_factory() as connection:
        revisions = connection.execute(
            """
            SELECT r.revision, r.state, r.parent_revision,
                   r.lock_hash, r.permission_diff_hash,
                   r.migration_plan_hash, r.contribution_diff_hash
              FROM bundle_installation_revision r
              JOIN bundle_installation i
                ON i.org_id = r.org_id AND i.project_id = r.project_id
               AND i.installation_pk = r.installation_pk
             WHERE i.org_id = %s AND i.project_id = %s
               AND i.installation_id = %s
             ORDER BY r.revision
            """,
            (runtime.org_id, runtime.project_id, installation_id),
        ).fetchall()
        events = connection.execute(
            """
            SELECT e.sequence, e.from_revision, e.to_revision,
                   e.from_state, e.to_state, e.evidence_json, e.evidence_hash
              FROM bundle_installation_event e
              JOIN bundle_installation i
                ON i.org_id = e.org_id AND i.project_id = e.project_id
               AND i.installation_pk = e.installation_pk
             WHERE i.org_id = %s AND i.project_id = %s
               AND i.installation_id = %s
             ORDER BY e.sequence
            """,
            (runtime.org_id, runtime.project_id, installation_id),
        ).fetchall()
    return [dict(row) for row in revisions], [dict(row) for row in events]


def test_revoked_selected_release_rolls_back_without_cross_installation_mutation(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        resolved = runtime.resolve(
            _request(snapshot.snapshot_hash),
            actor=MAKER,
            idempotency_key="m5-w3-resolve",
        )
        lock = StoredCompositionLock.model_validate_json(
            json.dumps(resolved.response_json)
        )
        contribution_diff = lock.payload.contribution_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        assert contribution_diff == {
            "baseline": [],
            "target": [],
            "added": [],
            "removed": [],
            "unchanged": [],
        }
        assert all(item.contributions == [] for item in lock.payload.resolved)
        assert lock.contribution_diff_hash == canonical_sha256(contribution_diff)

        overlay_revision = canonical_sha256(
            json.loads(OVERLAY_FIXTURE.read_text(encoding="utf-8"))
        )
        active_receipts = runtime.install_to_active(
            lock=lock,
            overlay_revision=overlay_revision,
            maker=MAKER,
            checker=CHECKER,
            idempotency_prefix="m5-w3-primary",
        )
        active = _response(active_receipts[-1])
        assert active.state == "active"
        assert active.current_revision == active.etag_version == 5
        assert active.active_revision == 5
        assert active.previous_active_revision is None

        sentinel_receipt = runtime.installation_service.create(
            request=CreateInstallationRequest.model_validate(
                {
                    "compositionId": lock.composition_id,
                    "lockRevision": lock.revision,
                    "overlayRevision": overlay_revision,
                    "displayName": "Synthetic unrelated draft sentinel",
                }
            ),
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            actor="maker:m5-w3-sentinel",
            roles={"asset-installer"},
            markings=set(),
            idempotency_key="m5-w3-sentinel-create",
        )
        sentinel = _response(sentinel_receipt)
        assert sentinel.state == "draft"
        sentinel_before = _installation_snapshot(runtime, sentinel.installation_id)
        assert sentinel_before == {
            "current_revision": 1,
            "active_revision": None,
            "previous_active_revision": None,
            "etag_version": 1,
            "revisions": 1,
            "events": 1,
        }

        revoked = runtime.registry_service.revoke(
            publisher="aos",
            bundle_id=REVOKED_ID,
            version="1.0.0",
            actor="m5-revoker",
            roles={"asset-publisher"},
            publisher_scopes={"aos"},
            reason="M5 rollback isolation proof",
        )
        assert revoked["status"] == "revoked"
        remaining_bundle_ids = (set(LEAF_IDS) | {"domain.ecommerce.core"}) - {
            REVOKED_ID
        }
        for bundle_id in remaining_bundle_ids:
            assert (
                runtime.registry_service.get_version(
                    publisher="aos", bundle_id=bundle_id, version="1.0.0"
                )["status"]
                == "published"
            )

        revalidator = InstallationRevalidator(
            release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots)
        )
        with (
            runtime.connect_factory() as connection,
            pytest.raises(RegistrySnapshotStaleError),
        ):
            revalidator.revalidate_in_transaction(connection, lock=lock)

        rolled_receipt = runtime.installation_service.rollback(
            installation_id=active.installation_id,
            request=RollbackInstallationRequest.model_validate(
                {"reason": "Selected release revoked; exit safely"}
            ),
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            actor=MAKER,
            roles={"asset-installer"},
            markings=set(),
            idempotency_key="m5-w3-primary-rollback",
            if_match='"5"',
        )
        rolled = _response(rolled_receipt)
        assert rolled_receipt.status_code == 200
        assert rolled_receipt.response_etag == '"6"'
        assert rolled.state == "rolled_back"
        assert rolled.current_revision == rolled.etag_version == 6
        assert rolled.active_revision is None
        assert rolled.previous_active_revision is None
        assert [event.to_state for event in rolled.events] == [
            "draft",
            "submitted",
            "approved",
            "applied",
            "active",
            "rolled_back",
        ]

        rollback_event = rolled.events[-1]
        rollback_evidence = rollback_event.evidence
        assert rollback_event.from_revision == 5
        assert rollback_event.to_revision == 6
        assert rollback_event.from_state == "active"
        assert rollback_event.to_state == "rolled_back"
        assert rollback_evidence is not None
        assert rollback_evidence.type == "rollback"
        assert rolled.decision is not None
        verify_event_evidence(
            rollback_evidence,
            installation_id=rolled.installation_id,
            from_revision=5,
            to_revision=6,
            lock_hash=lock.lock_hash,
            permission_diff_hash=lock.permission_diff_hash,
            migration_plan_hash=lock.migration_plan_hash,
            contribution_diff_hash=lock.contribution_diff_hash,
            decision_id=rolled.decision.decision_id,
            observed_at=rollback_evidence.observed_at,
        )

        revisions, events = _history(runtime, rolled.installation_id)
        assert [row["revision"] for row in revisions] == [1, 2, 3, 4, 5, 6]
        assert [row["state"] for row in revisions] == [
            "draft",
            "submitted",
            "approved",
            "applied",
            "active",
            "rolled_back",
        ]
        assert [row["parent_revision"] for row in revisions] == [
            None,
            1,
            2,
            3,
            4,
            5,
        ]
        assert all(
            row["contribution_diff_hash"] == lock.contribution_diff_hash
            for row in revisions
        )
        assert [row["sequence"] for row in events] == [1, 2, 3, 4, 5, 6]
        persisted_rollback = events[-1]
        assert persisted_rollback["evidence_json"] is not None
        assert persisted_rollback["evidence_hash"] == canonical_sha256(
            dict(persisted_rollback["evidence_json"])
        )

        fetched_lock = runtime.composition_service.get_lock(
            org_id=runtime.org_id,
            project_id=runtime.project_id,
            composition_id=lock.composition_id,
            revision=lock.revision,
            roles={"asset-installer"},
            markings=set(),
        )
        assert fetched_lock.contribution_diff_hash == lock.contribution_diff_hash
        assert fetched_lock.payload.contribution_diff == lock.payload.contribution_diff
        assert rolled.current.contribution_diff_hash == lock.contribution_diff_hash

        assert _installation_snapshot(runtime, active.installation_id) == {
            "current_revision": 6,
            "active_revision": None,
            "previous_active_revision": None,
            "etag_version": 6,
            "revisions": 6,
            "events": 6,
        }
        assert _installation_snapshot(runtime, sentinel.installation_id) == (
            sentinel_before
        )
