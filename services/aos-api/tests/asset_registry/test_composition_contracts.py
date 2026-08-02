"""Pure DTO tests for frozen M2 composition and installation contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    LOCK_SCHEMA_VERSION,
    MAX_BACKTRACKING_STATES,
    MAX_CANONICAL_LOCK_PAYLOAD_BYTES,
    MAX_CONTRIBUTION_CLAIMS,
    MAX_DEPENDENCY_DEPTH,
    MAX_DEPENDENCY_EDGES,
    MAX_REQUESTED_BUNDLES,
    MAX_RESOLVED_NODES,
    MAX_SNAPSHOT_CANDIDATES,
    RESOLVER_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    ApproveInstallationRequest,
    CompositionLockPayload,
    CompositionRequest,
    CurrentInstallationRef,
    DependencyConflictDetails,
    EmptyInstallationActionRequest,
    InstallationEvent,
    InstallationListResponse,
    InstallationRecord,
    InstallationRevision,
    PermissionDiff,
    PermissionSet,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
    StoredCompositionLock,
)

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
COMPOSITION_ID = "11111111-1111-4111-8111-111111111111"
INSTALLATION_ID = "22222222-2222-4222-8222-22222222abcd"
DECISION_ID = "33333333-3333-4333-8333-333333333333"


def _request_payload(*, requested: list[dict] | None = None) -> dict:
    return {
        "requested": requested
        or [{"publisher": "aos", "id": "solution.example", "version": "^1.0.0"}],
        "platformApiVersion": "1.7.0",
        "platformRelease": "aos-platform/1.7.0",
        "environment": "dev",
        "registrySnapshotHash": None,
        "currentInstallationRef": None,
    }


def _empty_permission_payload() -> dict:
    return {"roles": [], "markings": [], "dataScopes": [], "actionTypes": []}


def _empty_permission_diff_payload() -> dict:
    empty = _empty_permission_payload()
    return {
        "baseline": empty,
        "target": empty,
        "added": empty,
        "removed": empty,
        "unchanged": empty,
    }


def _empty_migration_diff_payload() -> dict:
    return {
        "baseline": [],
        "target": [],
        "added": [],
        "removed": [],
        "changed": [],
    }


def _empty_contribution_diff_payload() -> dict:
    return {
        "baseline": [],
        "target": [],
        "added": [],
        "removed": [],
        "unchanged": [],
    }


def _lock_payload() -> CompositionLockPayload:
    request = CompositionRequest.model_validate(_request_payload())
    return CompositionLockPayload.model_validate(
        {
            "lockSchemaVersion": LOCK_SCHEMA_VERSION,
            "resolverVersion": RESOLVER_VERSION,
            "request": request.lock_request(),
            "registrySnapshotHash": SHA_A,
            "resolved": [],
            "edges": [],
            "capabilityProviders": [],
            "permissionDiff": _empty_permission_diff_payload(),
            "migrationPlan": _empty_migration_diff_payload(),
            "contributionDiff": _empty_contribution_diff_payload(),
            "currentInstallationRef": None,
        }
    )


def _manifest(*, version: str) -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": "solution.example",
            "version": version,
            "displayName": "Example",
            "publisher": "aos",
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "exports": {},
            "capabilities": {"provides": [], "requires": []},
            "permissions": _empty_permission_payload(),
            "migrations": {"plan": None, "downgradePolicy": "retain-canonical"},
            "preflight": None,
            "regression": None,
            "rollback": None,
        },
    }


def _candidate(version: str) -> RegistrySnapshotCandidate:
    return RegistrySnapshotCandidate.model_validate(_candidate_payload(version))


def _candidate_payload(version: str) -> dict:
    return {
        "publisher": "aos",
        "id": "solution.example",
        "version": version,
        "kind": "SolutionPack",
        "manifest": _manifest(version=version),
        "contentHash": SHA_A,
        "signatureFingerprint": SHA_B,
        "releaseEvidenceRevision": SHA_C,
        "dependencies": [],
        "optionalDependencies": [],
        "conflicts": [],
        "capabilities": {"provides": [], "requires": []},
        "permissions": _empty_permission_payload(),
        "migration": {"planRef": None, "downgradePolicy": "retain-canonical"},
        "contributions": [],
    }


def test_composition_request_is_strict_alias_only_and_requires_publisher() -> None:
    request = CompositionRequest.model_validate(_request_payload())
    assert request.requested[0].publisher == "aos"

    missing_publisher = _request_payload(
        requested=[{"id": "solution.example", "version": "1.0.0"}]
    )
    with pytest.raises(ValidationError, match="Field required"):
        CompositionRequest.model_validate(missing_publisher)

    snake_alias = _request_payload()
    snake_alias["platform_api_version"] = snake_alias.pop("platformApiVersion")
    with pytest.raises(ValidationError):
        CompositionRequest.model_validate(snake_alias)

    tenant_injection = _request_payload()
    tenant_injection["orgId"] = "forged"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompositionRequest.model_validate(tenant_injection)

    non_exact_platform = _request_payload()
    non_exact_platform["platformApiVersion"] = "^1.7.0"
    with pytest.raises(ValidationError):
        CompositionRequest.model_validate(non_exact_platform)


def test_requested_bundles_sort_canonically_and_reject_duplicate_coordinate() -> None:
    request = CompositionRequest.model_validate(
        _request_payload(
            requested=[
                {"publisher": "zeta", "id": "pack.b", "version": "2.x"},
                {"publisher": "aos", "id": "pack.a", "version": "^1.0.0"},
            ]
        )
    )
    assert [(item.publisher, item.id) for item in request.requested] == [
        ("aos", "pack.a"),
        ("zeta", "pack.b"),
    ]

    duplicate = _request_payload(
        requested=[
            {"publisher": "aos", "id": "pack.a", "version": "^1.0.0"},
            {"publisher": "aos", "id": "pack.a", "version": "^2.0.0"},
        ]
    )
    with pytest.raises(ValidationError, match="coordinates must be unique"):
        CompositionRequest.model_validate(duplicate)


@pytest.mark.parametrize(
    "size",
    [MAX_REQUESTED_BUNDLES - 1, MAX_REQUESTED_BUNDLES],
)
def test_requested_bundle_max_minus_one_and_max_are_accepted(size: int) -> None:
    requested = [
        {"publisher": "aos", "id": f"pack.{index}", "version": "1.0.0"}
        for index in range(size)
    ]
    assert (
        len(
            CompositionRequest.model_validate(
                _request_payload(requested=requested)
            ).requested
        )
        == size
    )


def test_requested_bundle_max_plus_one_is_rejected() -> None:
    requested = [
        {"publisher": "aos", "id": f"pack.{index}", "version": "1.0.0"}
        for index in range(MAX_REQUESTED_BUNDLES + 1)
    ]
    with pytest.raises(ValidationError):
        CompositionRequest.model_validate(_request_payload(requested=requested))


def test_current_installation_ref_requires_canonical_uuid_and_aliases() -> None:
    ref = CurrentInstallationRef.model_validate(
        {
            "installationId": INSTALLATION_ID,
            "revision": 3,
            "lockHash": SHA_A,
            "overlayRevision": SHA_B,
        }
    )
    assert ref.installation_id == INSTALLATION_ID

    with pytest.raises(ValidationError, match="canonical lowercase"):
        CurrentInstallationRef.model_validate(
            {
                "installationId": INSTALLATION_ID.upper(),
                "revision": 3,
                "lockHash": SHA_A,
                "overlayRevision": SHA_B,
            }
        )


def test_registry_snapshot_sorts_semver_and_has_exact_hash_payload_dump() -> None:
    snapshot = RegistrySnapshot.build(
        candidates=[_candidate("2.0.0"), _candidate("1.0.0")],
        checked_at=datetime.now(UTC),
    )
    assert [item.version for item in snapshot.candidates] == ["1.0.0", "2.0.0"]
    payload = snapshot.hash_payload_dump()
    assert set(payload) == {"schemaVersion", "candidates"}
    assert payload["schemaVersion"] == SNAPSHOT_SCHEMA_VERSION
    assert "snapshotHash" not in payload
    assert "checkedAt" not in payload
    assert snapshot.snapshot_hash == canonical_sha256(payload)

    tampered = snapshot.model_dump(mode="python", by_alias=True)
    tampered["snapshotHash"] = SHA_D
    with pytest.raises(ValidationError, match="does not match canonical"):
        RegistrySnapshot.model_validate(tampered)


@pytest.mark.parametrize(
    "size",
    [MAX_SNAPSHOT_CANDIDATES - 1, MAX_SNAPSHOT_CANDIDATES],
)
def test_snapshot_candidate_max_minus_one_and_max_are_accepted(size: int) -> None:
    candidate = _candidate("1.0.0")
    snapshot = RegistrySnapshot.build(
        candidates=[candidate] * size,
        checked_at=datetime.now(UTC),
    )
    assert len(snapshot.candidates) == size


def test_snapshot_candidate_max_plus_one_is_rejected() -> None:
    candidate = _candidate("1.0.0")
    with pytest.raises(ValidationError):
        RegistrySnapshot.model_validate(
            {
                "candidates": [candidate] * (MAX_SNAPSHOT_CANDIDATES + 1),
                "snapshotHash": SHA_D,
                "checkedAt": datetime.now(UTC),
            }
        )


def test_snapshot_candidate_indexes_cannot_diverge_from_signed_manifest() -> None:
    payload = _candidate_payload("1.0.0")
    spec = payload["manifest"]["spec"]
    spec["dependencies"] = [{"id": "domain.core", "version": "^1.0.0"}]
    spec["optionalDependencies"] = [
        {"publisher": "partner", "id": "plugin.search", "version": "^2.0.0"}
    ]
    spec["conflicts"] = [{"id": "solution.legacy", "version": "<2.0.0"}]
    spec["capabilities"] = {
        "provides": ["solution.example.v1"],
        "requires": ["aos.core.v1"],
    }
    spec["permissions"] = {
        "roles": ["asset.reader"],
        "markings": ["internal"],
        "dataScopes": ["objects.read"],
        "actionTypes": [],
    }
    spec["migrations"] = {
        "plan": "migrations/plan.json",
        "downgradePolicy": "retain-canonical",
    }
    spec["contributions"] = [
        {
            "kind": "ui",
            "slot": "order.detail.actions",
            "id": "retry-order",
            "mode": "shared",
        }
    ]
    payload.update(
        {
            "dependencies": [
                {"publisher": "aos", "id": "domain.core", "version": "^1.0.0"}
            ],
            "optionalDependencies": [
                {
                    "publisher": "partner",
                    "id": "plugin.search",
                    "version": "^2.0.0",
                }
            ],
            "conflicts": [
                {
                    "publisher": "aos",
                    "id": "solution.legacy",
                    "version": "<2.0.0",
                }
            ],
            "capabilities": spec["capabilities"],
            "permissions": spec["permissions"],
            "migration": {
                "planRef": "migrations/plan.json",
                "downgradePolicy": "retain-canonical",
            },
            "contributions": spec["contributions"],
        }
    )
    RegistrySnapshotCandidate.model_validate(payload)

    mutations = {
        "dependencies": [],
        "optionalDependencies": [],
        "conflicts": [],
        "capabilities": {"provides": [], "requires": []},
        "permissions": _empty_permission_payload(),
        "migration": {"planRef": None, "downgradePolicy": "retain-canonical"},
        "contributions": [],
    }
    for field, forged_value in mutations.items():
        forged = deepcopy(payload)
        forged[field] = forged_value
        with pytest.raises(ValidationError, match="derived from signed manifest"):
            RegistrySnapshotCandidate.model_validate(forged)


def test_permission_sets_sort_and_diff_semantics_fail_closed() -> None:
    permissions = PermissionSet.model_validate(
        {
            "roles": ["zeta", "alpha"],
            "markings": [],
            "dataScopes": [],
            "actionTypes": [],
        }
    )
    assert permissions.roles == ["alpha", "zeta"]

    invalid = _empty_permission_diff_payload()
    invalid["target"] = {
        "roles": ["reader"],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    with pytest.raises(ValidationError, match="added set is inconsistent"):
        PermissionDiff.model_validate(invalid)


def test_lock_payload_preserves_null_and_excludes_client_preconditions() -> None:
    payload = _lock_payload()
    dumped = payload.hash_payload_dump()
    assert list(dumped) == [
        "lockSchemaVersion",
        "resolverVersion",
        "request",
        "registrySnapshotHash",
        "resolved",
        "edges",
        "capabilityProviders",
        "permissionDiff",
        "migrationPlan",
        "contributionDiff",
        "currentInstallationRef",
    ]
    assert dumped["currentInstallationRef"] is None
    assert "registrySnapshotHash" not in dumped["request"]
    assert "currentInstallationRef" not in dumped["request"]
    assert dumped["resolved"] == []
    assert dumped["permissionDiff"] == _empty_permission_diff_payload()


def test_stored_lock_recomputes_lock_and_all_three_diff_hashes() -> None:
    payload = _lock_payload()
    permission_diff = payload.permission_diff.model_dump(mode="json", by_alias=True)
    migration_plan = payload.migration_plan.model_dump(mode="json", by_alias=True)
    contribution_diff = payload.contribution_diff.model_dump(mode="json", by_alias=True)
    base = {
        "compositionId": COMPOSITION_ID,
        "revision": 1,
        "payload": payload,
        "lockHash": canonical_sha256(payload.hash_payload_dump()),
        "permissionDiffHash": canonical_sha256(permission_diff),
        "migrationPlanHash": canonical_sha256(migration_plan),
        "contributionDiffHash": canonical_sha256(contribution_diff),
        "createdAt": datetime.now(UTC),
    }
    stored = StoredCompositionLock.model_validate(base)
    assert stored.lock_hash == base["lockHash"]

    tampered = dict(base)
    tampered["lockHash"] = SHA_D
    with pytest.raises(ValidationError, match="hashes do not match"):
        StoredCompositionLock.model_validate(tampered)


def test_conflict_detail_sorting_and_nulls_are_stable() -> None:
    details = DependencyConflictDetails.model_validate(
        {
            "subtype": "version_intersection_empty",
            "path": [],
            "constraints": [],
            "candidateRejections": [],
            "resource": None,
        }
    )
    assert details.model_dump(mode="json", by_alias=True) == {
        "subtype": "version_intersection_empty",
        "path": [],
        "constraints": [],
        "candidateRejections": [],
        "resource": None,
    }


def _revision(*, state: str, revision: int, decision_id: str | None) -> dict:
    return {
        "installationId": INSTALLATION_ID,
        "revision": revision,
        "parentRevision": None if revision == 1 else revision - 1,
        "state": state,
        "compositionId": COMPOSITION_ID,
        "lockRevision": 1,
        "lockHash": SHA_A,
        "permissionDiffHash": SHA_B,
        "migrationPlanHash": SHA_C,
        "contributionDiffHash": SHA_D,
        "overlayRevision": SHA_A,
        "requestedBy": "requester",
        "decisionId": decision_id,
        "createdAt": datetime.now(UTC),
    }


def test_installation_action_and_revision_contracts_are_strict() -> None:
    assert EmptyInstallationActionRequest.model_validate({}).model_dump() == {}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EmptyInstallationActionRequest.model_validate({"expectedRevision": 2})

    approval = {
        "lockHash": SHA_A,
        "permissionDiffHash": SHA_B,
        "migrationPlanHash": SHA_C,
        "contributionDiffHash": SHA_D,
    }
    assert ApproveInstallationRequest.model_validate(approval).lock_hash == SHA_A

    revision = InstallationRevision.model_validate(
        _revision(state="approved", revision=3, decision_id=DECISION_ID)
    )
    assert revision.parent_revision == 2
    with pytest.raises(ValidationError, match="decisionId is inconsistent"):
        InstallationRevision.model_validate(
            _revision(state="submitted", revision=2, decision_id=DECISION_ID)
        )


def test_installation_record_sorts_events_and_list_uses_frozen_order() -> None:
    created = datetime(2026, 8, 3, 1, tzinfo=UTC)
    revision_payload = _revision(state="submitted", revision=2, decision_id=None)
    revision_payload["createdAt"] = created
    revision = InstallationRevision.model_validate(revision_payload)
    event_one = InstallationEvent.model_validate(
        {
            "sequence": 1,
            "fromRevision": None,
            "toRevision": 1,
            "fromState": None,
            "toState": "draft",
            "actor": "requester",
            "reason": None,
            "evidence": None,
            "createdAt": created,
        }
    )
    event_two = InstallationEvent.model_validate(
        {
            "sequence": 2,
            "fromRevision": 1,
            "toRevision": 2,
            "fromState": "draft",
            "toState": "submitted",
            "actor": "requester",
            "reason": None,
            "evidence": None,
            "createdAt": created,
        }
    )
    record = InstallationRecord.model_validate(
        {
            "installationId": INSTALLATION_ID,
            "displayName": "Example",
            "state": "submitted",
            "currentRevision": 2,
            "activeRevision": None,
            "previousActiveRevision": None,
            "etagVersion": 2,
            "createdAt": created,
            "updatedAt": created,
            "current": revision,
            "decision": None,
            "events": [event_two, event_one],
        }
    )
    assert [item.sequence for item in record.events] == [1, 2]

    listed = InstallationListResponse.model_validate(
        {"items": [record], "total": 1, "limit": 50, "offset": 0}
    )
    assert listed.items[0].installation_id == INSTALLATION_ID


def test_all_frozen_resource_limit_constants_are_exact() -> None:
    assert MAX_REQUESTED_BUNDLES == 64
    assert MAX_SNAPSHOT_CANDIDATES == 4096
    assert MAX_RESOLVED_NODES == 512
    assert MAX_DEPENDENCY_EDGES == 4096
    assert MAX_DEPENDENCY_DEPTH == 64
    assert MAX_BACKTRACKING_STATES == 10000
    assert MAX_CONTRIBUTION_CLAIMS == 10000
    assert MAX_CANONICAL_LOCK_PAYLOAD_BYTES == 4 * 1024 * 1024
