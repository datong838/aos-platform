"""M5-2 real PostgreSQL composition and installation control-plane proof."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    ApproveInstallationRequest,
    CompositionRequest,
    CreateInstallationRequest,
    EmptyInstallationActionRequest,
    InstallationResponse,
    RollbackInstallationRequest,
    StoredCompositionLock,
)
from aos_api.asset_registry.control_policy import strong_etag
from aos_api.asset_registry.errors import (
    DutySeparationRequiredError,
    IdempotencyConflictError,
    RevisionConflictError,
)
from aos_api.asset_registry.installation_evidence import verify_event_evidence
from aos_api.asset_registry.installation_store import CommandReceipt
from tests.asset_registry.m5_control_support import (
    M5_ORG_ID,
    M5_PROJECT_ID,
    M5ControlRuntime,
    m5_control_runtime,
)
from tests.asset_registry.test_m5_ecommerce_composition import (
    CORE_ID,
    DEPENDENCY_RANGE,
    EXPECTED_RESOLVED_IDS,
    LEAF_IDS,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY_FIXTURE = (
    REPO_ROOT
    / "services/aos-api/tests/asset_registry/fixtures/m5/instance-overlay.synthetic.json"
)
ORG = M5_ORG_ID
PROJECT = M5_PROJECT_ID
MAKER = "maker:m5"
CHECKER = "checker:m5"
MAKER_ROLES = {"asset-installer", "asset-install-approver"}
CHECKER_ROLES = {"asset-install-approver"}


def _three_leaf_request(snapshot) -> CompositionRequest:
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


def _installation_response(
    receipt: CommandReceipt,
    *,
    state: str,
    revision: int,
) -> InstallationResponse:
    expected_status = 201 if revision == 1 else 200
    assert receipt.status_code == expected_status
    assert receipt.replayed is False
    assert receipt.response_etag == strong_etag(revision)
    response = InstallationResponse.model_validate_json(
        json.dumps(receipt.response_json)
    )
    assert response.state == state
    assert response.current_revision == revision
    assert response.etag_version == revision
    assert response.current.revision == revision
    assert response.current.state == state
    assert len(response.events) == revision
    return response


def _mutable_counts(runtime: M5ControlRuntime) -> dict[str, int]:
    with runtime.connect_factory() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM bundle_installation_command) AS commands,
              (SELECT COUNT(*) FROM bundle_installation_revision) AS revisions,
              (SELECT COUNT(*) FROM bundle_installation_event) AS events,
              (SELECT COUNT(*) FROM bundle_installation_decision) AS decisions
            """
        ).fetchone()
    assert row is not None
    return dict(row)


def _assert_lock(lock: StoredCompositionLock) -> None:
    assert lock.revision == 1
    assert tuple(item.id for item in lock.payload.resolved) == EXPECTED_RESOLVED_IDS
    assert sum(item.id == CORE_ID for item in lock.payload.resolved) == 1
    assert {item.id: item.selection_reason for item in lock.payload.resolved} == {
        CORE_ID: "dependency",
        **{bundle_id: "requested" for bundle_id in LEAF_IDS},
    }
    assert {
        (edge.from_id, edge.to_id, edge.constraint, edge.optional)
        for edge in lock.payload.edges
    } == {(bundle_id, CORE_ID, DEPENDENCY_RANGE, False) for bundle_id in LEAF_IDS}
    assert lock.payload.current_installation_ref is None
    assert lock.payload.capability_providers == []

    empty_permissions = {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    assert lock.payload.permission_diff.model_dump(mode="json", by_alias=True) == {
        "baseline": empty_permissions,
        "target": empty_permissions,
        "added": empty_permissions,
        "removed": empty_permissions,
        "unchanged": empty_permissions,
    }
    assert lock.payload.migration_plan.model_dump(mode="json", by_alias=True) == {
        "baseline": [],
        "target": [],
        "added": [],
        "removed": [],
        "changed": [],
    }
    contribution_diff = lock.payload.contribution_diff.model_dump(
        mode="json", by_alias=True
    )
    assert contribution_diff["baseline"] == []
    assert contribution_diff["removed"] == []
    assert contribution_diff["unchanged"] == []
    assert contribution_diff["target"] == contribution_diff["added"]
    assert len(contribution_diff["target"]) == 16
    assert lock.lock_hash == canonical_sha256(lock.payload.hash_payload_dump())
    assert lock.permission_diff_hash == canonical_sha256(
        lock.payload.permission_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
    )
    assert lock.migration_plan_hash == canonical_sha256(
        lock.payload.migration_plan.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
    )
    assert lock.contribution_diff_hash == canonical_sha256(
        lock.payload.contribution_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
    )


def _assert_event_evidence(response: InstallationResponse) -> None:
    decision = response.decision
    assert decision is not None
    evidence_events = [event for event in response.events if event.evidence is not None]
    assert [event.evidence.type for event in evidence_events] == [
        "dry_apply",
        "verification",
        "rollback",
    ]
    for event in evidence_events:
        evidence = event.evidence
        assert evidence is not None
        assert event.from_revision is not None
        verify_event_evidence(
            evidence,
            installation_id=response.installation_id,
            from_revision=event.from_revision,
            to_revision=event.to_revision,
            lock_hash=response.current.lock_hash,
            permission_diff_hash=response.current.permission_diff_hash,
            migration_plan_hash=response.current.migration_plan_hash,
            contribution_diff_hash=response.current.contribution_diff_hash,
            decision_id=decision.decision_id,
            observed_at=evidence.observed_at,
        )


def _assert_database_evidence(runtime: M5ControlRuntime) -> None:
    with runtime.connect_factory() as connection:
        rows = connection.execute(
            """
            SELECT sequence, evidence_json, evidence_hash
              FROM bundle_installation_event
             WHERE evidence_json IS NOT NULL
             ORDER BY sequence
            """
        ).fetchall()
    assert [row["sequence"] for row in rows] == [4, 5, 6]
    assert all(
        row["evidence_hash"] == canonical_sha256(dict(row["evidence_json"]))
        for row in rows
    )


def _assert_final_counts(runtime: M5ControlRuntime) -> None:
    with runtime.connect_factory() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM asset_bundle) AS bundles,
              (SELECT COUNT(*) FROM asset_bundle_version) AS versions,
              (SELECT COUNT(*) FROM asset_bundle_version
                WHERE status = 'published') AS published_versions,
              (SELECT COUNT(*) FROM asset_bundle_evidence) AS release_evidence,
              (SELECT COUNT(*) FROM bundle_composition) AS compositions,
              (SELECT COUNT(*) FROM bundle_composition_lock) AS locks,
              (SELECT COUNT(*) FROM bundle_installation) AS installations,
              (SELECT COUNT(*) FROM bundle_installation_revision) AS revisions,
              (SELECT COUNT(*) FROM bundle_installation_decision) AS decisions,
              (SELECT COUNT(*) FROM bundle_installation_event) AS events,
              (SELECT COUNT(*) FROM bundle_installation_event
                WHERE evidence_json IS NOT NULL) AS evidence_events,
              (SELECT COUNT(*) FROM bundle_installation_command) AS commands,
              (SELECT COUNT(DISTINCT idempotency_key)
                 FROM bundle_installation_command) AS command_keys
            """
        ).fetchone()
    assert row == {
        "bundles": 4,
        "versions": 4,
        "published_versions": 4,
        "release_evidence": 20,
        "compositions": 1,
        "locks": 1,
        "installations": 1,
        "revisions": 6,
        "decisions": 1,
        "events": 6,
        "evidence_events": 3,
        "commands": 7,
        "command_keys": 7,
    }


def test_m5_composition_and_installation_complete_real_pg_lifecycle(
    tmp_path: Path,
) -> None:
    with m5_control_runtime(tmp_path / "runtime-bundles") as runtime:
        snapshot = runtime.snapshot_reader.read()
        request = _three_leaf_request(snapshot)

        resolved = runtime.resolve(
            request,
            actor=MAKER,
            roles=MAKER_ROLES,
            idempotency_key="m5-resolve-01",
        )
        assert resolved.status_code == 201
        assert resolved.replayed is False
        assert resolved.response_etag is None
        lock = StoredCompositionLock.model_validate_json(
            json.dumps(resolved.response_json)
        )
        _assert_lock(lock)

        replayed = runtime.resolve(
            request,
            actor=MAKER,
            roles=MAKER_ROLES,
            idempotency_key="m5-resolve-01",
        )
        assert replayed.replayed is True
        assert replayed.response_json == resolved.response_json

        changed = request.model_dump(mode="python", by_alias=True, exclude_none=False)
        changed["environment"] = "staging"
        with pytest.raises(IdempotencyConflictError):
            runtime.resolve(
                CompositionRequest.model_validate(changed),
                actor=MAKER,
                roles=MAKER_ROLES,
                idempotency_key="m5-resolve-01",
            )

        fetched_lock = runtime.composition_service.get_lock(
            org_id=ORG,
            project_id=PROJECT,
            composition_id=lock.composition_id,
            revision=lock.revision,
            roles=MAKER_ROLES,
            markings=set(),
        )
        assert fetched_lock == lock
        assert _mutable_counts(runtime) == {
            "commands": 1,
            "revisions": 0,
            "events": 0,
            "decisions": 0,
        }

        overlay_revision = canonical_sha256(
            json.loads(OVERLAY_FIXTURE.read_text(encoding="utf-8"))
        )
        created_receipt = runtime.installation_service.create(
            request=CreateInstallationRequest.model_validate(
                {
                    "compositionId": lock.composition_id,
                    "lockRevision": lock.revision,
                    "overlayRevision": overlay_revision,
                    "displayName": "Synthetic M5 ecommerce composition",
                }
            ),
            org_id=ORG,
            project_id=PROJECT,
            actor=MAKER,
            roles=MAKER_ROLES,
            markings=set(),
            idempotency_key="m5-install-create-01",
        )
        created = _installation_response(created_receipt, state="draft", revision=1)
        installation_id = created.installation_id
        assert created.active_revision is None
        assert created.previous_active_revision is None

        submitted_receipt = runtime.installation_service.submit(
            installation_id=installation_id,
            request=EmptyInstallationActionRequest(),
            org_id=ORG,
            project_id=PROJECT,
            actor=MAKER,
            roles=MAKER_ROLES,
            markings=set(),
            idempotency_key="m5-install-submit-02",
            if_match='"1"',
        )
        submitted = _installation_response(
            submitted_receipt, state="submitted", revision=2
        )
        approval = ApproveInstallationRequest.model_validate(
            {
                "lockHash": lock.lock_hash,
                "permissionDiffHash": lock.permission_diff_hash,
                "migrationPlanHash": lock.migration_plan_hash,
                "contributionDiffHash": lock.contribution_diff_hash,
            }
        )
        before_rejected_approvals = _mutable_counts(runtime)

        with pytest.raises(RevisionConflictError):
            runtime.installation_service.approve(
                installation_id=installation_id,
                request=approval,
                org_id=ORG,
                project_id=PROJECT,
                actor=CHECKER,
                roles=CHECKER_ROLES,
                markings=set(),
                idempotency_key="m5-install-stale-approve-03",
                if_match='"1"',
            )
        assert _mutable_counts(runtime) == before_rejected_approvals

        with pytest.raises(DutySeparationRequiredError):
            runtime.installation_service.approve(
                installation_id=installation_id,
                request=approval,
                org_id=ORG,
                project_id=PROJECT,
                actor=MAKER,
                roles=MAKER_ROLES,
                markings=set(),
                idempotency_key="m5-install-self-approve-04",
                if_match='"2"',
            )
        assert _mutable_counts(runtime) == before_rejected_approvals
        still_submitted = runtime.installation_service.get(
            installation_id=installation_id,
            org_id=ORG,
            project_id=PROJECT,
            roles=MAKER_ROLES,
            markings=set(),
        )
        assert still_submitted == submitted

        approved_receipt = runtime.installation_service.approve(
            installation_id=installation_id,
            request=approval,
            org_id=ORG,
            project_id=PROJECT,
            actor=CHECKER,
            roles=CHECKER_ROLES,
            markings=set(),
            idempotency_key="m5-install-approve-05",
            if_match='"2"',
        )
        approved = _installation_response(
            approved_receipt, state="approved", revision=3
        )
        assert approved.decision is not None
        assert approved.decision.actor == CHECKER
        assert approved.decision.submitted_revision == 2
        assert (
            approved.decision.lock_hash,
            approved.decision.permission_diff_hash,
            approved.decision.migration_plan_hash,
            approved.decision.contribution_diff_hash,
        ) == (
            lock.lock_hash,
            lock.permission_diff_hash,
            lock.migration_plan_hash,
            lock.contribution_diff_hash,
        )

        applied_receipt = runtime.installation_service.apply(
            installation_id=installation_id,
            request=EmptyInstallationActionRequest(),
            org_id=ORG,
            project_id=PROJECT,
            actor=MAKER,
            roles=MAKER_ROLES,
            markings=set(),
            idempotency_key="m5-install-apply-06",
            if_match='"3"',
        )
        applied = _installation_response(applied_receipt, state="applied", revision=4)
        assert applied.active_revision is None
        assert applied.previous_active_revision is None

        active_receipt = runtime.installation_service.verify(
            installation_id=installation_id,
            request=EmptyInstallationActionRequest(),
            org_id=ORG,
            project_id=PROJECT,
            actor=MAKER,
            roles=MAKER_ROLES,
            markings=set(),
            idempotency_key="m5-install-verify-07",
            if_match='"4"',
        )
        active = _installation_response(active_receipt, state="active", revision=5)
        assert active.active_revision == 5
        assert active.previous_active_revision is None

        rolled_back_receipt = runtime.installation_service.rollback(
            installation_id=installation_id,
            request=RollbackInstallationRequest(reason="Synthetic M5 rollback"),
            org_id=ORG,
            project_id=PROJECT,
            actor=MAKER,
            roles=MAKER_ROLES,
            markings=set(),
            idempotency_key="m5-install-rollback-08",
            if_match='"5"',
        )
        rolled_back = _installation_response(
            rolled_back_receipt, state="rolled_back", revision=6
        )
        assert rolled_back.active_revision is None
        assert rolled_back.previous_active_revision is None
        assert [event.sequence for event in rolled_back.events] == list(range(1, 7))
        assert [event.to_revision for event in rolled_back.events] == list(range(1, 7))
        assert [event.from_revision for event in rolled_back.events] == [
            None,
            1,
            2,
            3,
            4,
            5,
        ]
        assert [event.to_state for event in rolled_back.events] == [
            "draft",
            "submitted",
            "approved",
            "applied",
            "active",
            "rolled_back",
        ]
        assert [event.actor for event in rolled_back.events] == [
            MAKER,
            MAKER,
            CHECKER,
            MAKER,
            MAKER,
            MAKER,
        ]
        assert [event.reason for event in rolled_back.events] == [
            None,
            None,
            None,
            None,
            None,
            "Synthetic M5 rollback",
        ]
        _assert_event_evidence(rolled_back)

        with runtime.connect_factory() as connection:
            revisions = connection.execute(
                """
                SELECT revision, parent_revision, state, lock_revision,
                       lock_hash, permission_diff_hash, migration_plan_hash,
                       contribution_diff_hash, overlay_revision, decision_id
                  FROM bundle_installation_revision
                 ORDER BY revision
                """
            ).fetchall()
            pointer = connection.execute(
                """
                SELECT current_revision, active_revision,
                       previous_active_revision, etag_version
                  FROM bundle_installation
                """
            ).fetchone()
        assert [row["parent_revision"] for row in revisions] == [None, 1, 2, 3, 4, 5]
        assert all(row["lock_revision"] == 1 for row in revisions)
        assert all(row["lock_hash"] == lock.lock_hash for row in revisions)
        assert all(
            row["permission_diff_hash"] == lock.permission_diff_hash
            and row["migration_plan_hash"] == lock.migration_plan_hash
            and row["contribution_diff_hash"] == lock.contribution_diff_hash
            and row["overlay_revision"] == overlay_revision
            for row in revisions
        )
        decision_id = revisions[2]["decision_id"]
        assert decision_id is not None
        assert [row["decision_id"] for row in revisions] == [
            None,
            None,
            decision_id,
            decision_id,
            decision_id,
            decision_id,
        ]
        assert pointer == {
            "current_revision": 6,
            "active_revision": None,
            "previous_active_revision": None,
            "etag_version": 6,
        }

        _assert_database_evidence(runtime)
        _assert_final_counts(runtime)
