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
    ContributionDiff,
    CurrentInstallationRef,
    DependencyConflictDetails,
    EmptyInstallationActionRequest,
    InstallationEvent,
    InstallationListItem,
    InstallationListResponse,
    InstallationRecord,
    InstallationRevision,
    MigrationPlanDiff,
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
            "resolved": [_resolved_bundle_payload()],
            "edges": [],
            "capabilityProviders": [],
            "permissionDiff": _empty_permission_diff_payload(),
            "migrationPlan": _empty_migration_diff_payload(),
            "contributionDiff": _empty_contribution_diff_payload(),
            "currentInstallationRef": None,
        }
    )


def _resolved_bundle_payload() -> dict:
    return {
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
        "permissions": _empty_permission_payload(),
        "migration": {"planRef": None, "downgradePolicy": "retain-canonical"},
        "contributions": [],
        "selectionReason": "requested",
    }


def _manifest(*, version: str, bundle_id: str = "solution.example") -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": bundle_id,
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


def _candidate(
    version: str,
    *,
    bundle_id: str = "solution.example",
    content_hash: str = SHA_A,
) -> RegistrySnapshotCandidate:
    return RegistrySnapshotCandidate.model_validate(
        _candidate_payload(
            version,
            bundle_id=bundle_id,
            content_hash=content_hash,
        )
    )


def _candidate_payload(
    version: str,
    *,
    bundle_id: str = "solution.example",
    content_hash: str = SHA_A,
) -> dict:
    return {
        "publisher": "aos",
        "id": bundle_id,
        "version": version,
        "kind": "SolutionPack",
        "manifest": _manifest(version=version, bundle_id=bundle_id),
        "contentHash": content_hash,
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


@pytest.fixture(scope="module")
def unique_snapshot_candidates() -> list[RegistrySnapshotCandidate]:
    return [
        _candidate("1.0.0", bundle_id=f"solution.example-{index}")
        for index in range(MAX_SNAPSHOT_CANDIDATES + 1)
    ]


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
def test_snapshot_candidate_max_minus_one_and_max_are_accepted(
    size: int,
    unique_snapshot_candidates: list[RegistrySnapshotCandidate],
) -> None:
    snapshot = RegistrySnapshot.build(
        candidates=unique_snapshot_candidates[:size],
        checked_at=datetime.now(UTC),
    )
    assert len(snapshot.candidates) == size


def test_snapshot_candidate_max_plus_one_is_rejected(
    unique_snapshot_candidates: list[RegistrySnapshotCandidate],
) -> None:
    with pytest.raises(ValidationError):
        RegistrySnapshot.model_validate(
            {
                "candidates": unique_snapshot_candidates,
                "snapshotHash": SHA_D,
                "checkedAt": datetime.now(UTC),
            }
        )


def test_snapshot_rejects_duplicate_coordinate_version_even_if_content_differs() -> (
    None
):
    candidate = _candidate("1.0.0")
    with pytest.raises(ValidationError, match="candidate coordinates must be unique"):
        RegistrySnapshot.build(
            candidates=[candidate, candidate],
            checked_at=datetime.now(UTC),
        )

    changed_content = _candidate("1.0.0", content_hash=SHA_D)
    with pytest.raises(ValidationError, match="candidate coordinates must be unique"):
        RegistrySnapshot.build(
            candidates=[candidate, changed_content],
            checked_at=datetime.now(UTC),
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

    for field in ("dependencies", "optionalDependencies", "conflicts"):
        duplicate = deepcopy(payload)
        duplicate[field].append(deepcopy(duplicate[field][0]))
        with pytest.raises(ValidationError, match="candidate .* must be unique"):
            RegistrySnapshotCandidate.model_validate(duplicate)


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


def _migration_step(bundle_id: str, version: str, plan_ref: str) -> dict:
    return {
        "publisher": "aos",
        "id": bundle_id,
        "version": version,
        "planRef": plan_ref,
        "downgradePolicy": "retain-canonical",
    }


def test_migration_diff_is_exactly_derived_by_bundle_coordinate() -> None:
    removed = _migration_step("pack.removed", "1.0.0", "migrations/old.json")
    before = _migration_step("pack.changed", "1.0.0", "migrations/v1.json")
    after = _migration_step("pack.changed", "2.0.0", "migrations/v2.json")
    added = _migration_step("pack.added", "1.0.0", "migrations/new.json")
    payload = {
        "baseline": [before, removed],
        "target": [added, after],
        "added": [added],
        "removed": [removed],
        "changed": [
            {
                "publisher": "aos",
                "id": "pack.changed",
                "before": before,
                "after": after,
            }
        ],
    }
    diff = MigrationPlanDiff.model_validate(payload)
    assert [item.id for item in diff.added] == ["pack.added"]
    assert [item.id for item in diff.removed] == ["pack.removed"]
    assert [item.id for item in diff.changed] == ["pack.changed"]

    for field in ("added", "removed", "changed"):
        forged = deepcopy(payload)
        forged[field] = []
        with pytest.raises(
            ValidationError, match=f"migration {field} set is inconsistent"
        ):
            MigrationPlanDiff.model_validate(forged)

    duplicate_coordinate = deepcopy(payload)
    duplicate_coordinate["baseline"].append(
        _migration_step("pack.changed", "1.1.0", "migrations/v1-1.json")
    )
    with pytest.raises(ValidationError, match="migration baseline must be unique"):
        MigrationPlanDiff.model_validate(duplicate_coordinate)


def _contribution_binding(binding_id: str, claim_id: str) -> dict:
    return {
        "publisher": "aos",
        "id": binding_id,
        "version": "1.0.0",
        "claim": {
            "kind": "ui",
            "slot": "order.detail.actions",
            "id": claim_id,
            "mode": "shared",
        },
    }


def test_contribution_diff_is_exact_canonical_binding_set_math() -> None:
    removed = _contribution_binding("pack.removed", "remove-action")
    unchanged = _contribution_binding("pack.common", "common-action")
    added = _contribution_binding("pack.added", "add-action")
    payload = {
        "baseline": [unchanged, removed],
        "target": [added, unchanged],
        "added": [added],
        "removed": [removed],
        "unchanged": [unchanged],
    }
    diff = ContributionDiff.model_validate(payload)
    assert [item.id for item in diff.added] == ["pack.added"]
    assert [item.id for item in diff.removed] == ["pack.removed"]
    assert [item.id for item in diff.unchanged] == ["pack.common"]

    for field in ("added", "removed", "unchanged"):
        forged = deepcopy(payload)
        forged[field] = []
        with pytest.raises(
            ValidationError,
            match=f"contribution {field} set is inconsistent",
        ):
            ContributionDiff.model_validate(forged)

    mode_changed = deepcopy(payload)
    changed_binding = deepcopy(unchanged)
    changed_binding["claim"]["mode"] = "exclusive"
    mode_changed["target"] = [added, changed_binding]
    mode_changed["added"] = [added, changed_binding]
    mode_changed["removed"] = [removed, unchanged]
    with pytest.raises(
        ValidationError, match="contribution unchanged set is inconsistent"
    ):
        ContributionDiff.model_validate(mode_changed)


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
    assert len(dumped["resolved"]) == 1
    assert dumped["permissionDiff"] == _empty_permission_diff_payload()


def test_lock_requires_resolved_bundle_but_does_not_cap_capability_count_at_512() -> (
    None
):
    empty = _lock_payload().model_dump(mode="python", by_alias=True)
    empty["resolved"] = []
    with pytest.raises(ValidationError):
        CompositionLockPayload.model_validate(empty)

    many_capabilities = _lock_payload().model_dump(mode="python", by_alias=True)
    many_capabilities["capabilityProviders"] = [
        {
            "capability": f"capability.{index}",
            "publisher": "aos",
            "id": "solution.example",
            "version": "1.0.0",
        }
        for index in range(MAX_RESOLVED_NODES + 1)
    ]
    payload = CompositionLockPayload.model_validate(many_capabilities)
    assert len(payload.capability_providers) == MAX_RESOLVED_NODES + 1


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


def _list_item_payload(
    *,
    state: str,
    current_revision: int,
    active_revision: int | None,
    previous_active_revision: int | None,
    etag_version: int | None = None,
) -> dict:
    created = datetime(2026, 8, 3, 1, tzinfo=UTC)
    return {
        "installationId": INSTALLATION_ID,
        "displayName": "Example",
        "state": state,
        "currentRevision": current_revision,
        "activeRevision": active_revision,
        "previousActiveRevision": previous_active_revision,
        "etagVersion": etag_version or current_revision,
        "createdAt": created,
        "updatedAt": created,
    }


def test_installation_list_item_etag_and_state_pointers_fail_closed() -> None:
    active = InstallationListItem.model_validate(
        _list_item_payload(
            state="active",
            current_revision=6,
            active_revision=6,
            previous_active_revision=3,
        )
    )
    assert active.etag_version == active.current_revision

    rolled_back = InstallationListItem.model_validate(
        _list_item_payload(
            state="rolled_back",
            current_revision=7,
            active_revision=3,
            previous_active_revision=3,
        )
    )
    assert rolled_back.active_revision == 3
    rolled_back_to_empty = InstallationListItem.model_validate(
        _list_item_payload(
            state="rolled_back",
            current_revision=7,
            active_revision=None,
            previous_active_revision=None,
        )
    )
    assert rolled_back_to_empty.active_revision is None

    invalid_payloads = [
        _list_item_payload(
            state="submitted",
            current_revision=2,
            active_revision=None,
            previous_active_revision=None,
            etag_version=3,
        ),
        _list_item_payload(
            state="applied",
            current_revision=5,
            active_revision=4,
            previous_active_revision=None,
        ),
        _list_item_payload(
            state="active",
            current_revision=6,
            active_revision=5,
            previous_active_revision=None,
        ),
        _list_item_payload(
            state="active",
            current_revision=6,
            active_revision=6,
            previous_active_revision=6,
        ),
        _list_item_payload(
            state="rolled_back",
            current_revision=7,
            active_revision=7,
            previous_active_revision=None,
        ),
        _list_item_payload(
            state="rolled_back",
            current_revision=7,
            active_revision=3,
            previous_active_revision=None,
        ),
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            InstallationListItem.model_validate(payload)


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

    sequence_gap = record.model_dump(mode="python", by_alias=True)
    sequence_gap["events"][1]["sequence"] = 3
    with pytest.raises(ValidationError, match="start at 1 and be continuous"):
        InstallationRecord.model_validate(sequence_gap)

    stale_tail = record.model_dump(mode="python", by_alias=True)
    stale_tail["events"][1]["toRevision"] = 1
    with pytest.raises(ValidationError, match="history is not continuous"):
        InstallationRecord.model_validate(stale_tail)

    incomplete = record.model_dump(mode="python", by_alias=True)
    incomplete["events"] = incomplete["events"][:1]
    with pytest.raises(ValidationError, match="event count must equal"):
        InstallationRecord.model_validate(incomplete)


def _approved_record_payload() -> dict:
    created = datetime(2026, 8, 3, 1, tzinfo=UTC)
    current = _revision(state="approved", revision=3, decision_id=DECISION_ID)
    current["createdAt"] = created
    decision = {
        "decisionId": DECISION_ID,
        "installationId": INSTALLATION_ID,
        "submittedRevision": 2,
        "decision": "approved",
        "actor": "reviewer",
        "lockHash": SHA_A,
        "permissionDiffHash": SHA_B,
        "migrationPlanHash": SHA_C,
        "contributionDiffHash": SHA_D,
        "reason": None,
        "createdAt": created,
    }
    events = [
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
        },
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
        },
        {
            "sequence": 3,
            "fromRevision": 2,
            "toRevision": 3,
            "fromState": "submitted",
            "toState": "approved",
            "actor": "reviewer",
            "reason": None,
            "evidence": None,
            "createdAt": created,
        },
    ]
    return {
        **_list_item_payload(
            state="approved",
            current_revision=3,
            active_revision=None,
            previous_active_revision=None,
        ),
        "current": current,
        "decision": decision,
        "events": events,
    }


def _append_installation_state(payload: dict, state: str) -> dict:
    updated = deepcopy(payload)
    previous_revision = updated["currentRevision"]
    previous_state = updated["state"]
    revision = previous_revision + 1
    updated["state"] = state
    updated["currentRevision"] = revision
    updated["etagVersion"] = revision
    updated["current"]["revision"] = revision
    updated["current"]["parentRevision"] = previous_revision
    updated["current"]["state"] = state
    if state == "active":
        updated["activeRevision"] = revision
        updated["previousActiveRevision"] = None
    elif state == "rolled_back":
        updated["activeRevision"] = updated["previousActiveRevision"]
    updated["events"].append(
        {
            "sequence": revision,
            "fromRevision": previous_revision,
            "toRevision": revision,
            "fromState": previous_state,
            "toState": state,
            "actor": "operator",
            "reason": None,
            "evidence": None,
            "createdAt": updated["createdAt"],
        }
    )
    return updated


def test_installation_record_decision_identity_hash_state_and_event_tail() -> None:
    payload = _approved_record_payload()
    record = InstallationRecord.model_validate(payload)
    assert record.decision is not None
    assert record.decision.decision == "approved"
    assert record.events[-1].to_revision == record.current_revision

    applied = _append_installation_state(payload, "applied")
    active = _append_installation_state(applied, "active")
    rolled_back = _append_installation_state(active, "rolled_back")
    assert InstallationRecord.model_validate(applied).state == "applied"
    assert InstallationRecord.model_validate(active).state == "active"
    assert InstallationRecord.model_validate(rolled_back).state == "rolled_back"

    rejected_record = deepcopy(payload)
    rejected_record["state"] = "rejected"
    rejected_record["current"]["state"] = "rejected"
    rejected_record["decision"]["decision"] = "rejected"
    rejected_record["decision"]["reason"] = "not approved"
    rejected_record["events"][-1]["toState"] = "rejected"
    assert InstallationRecord.model_validate(rejected_record).state == "rejected"

    mutations = [
        ("installationId", "44444444-4444-4444-8444-44444444abcd"),
        ("decisionId", "55555555-5555-4555-8555-55555555abcd"),
        ("lockHash", SHA_D),
        ("permissionDiffHash", SHA_D),
        ("migrationPlanHash", SHA_D),
        ("contributionDiffHash", SHA_A),
        ("actor", "requester"),
    ]
    for field, value in mutations:
        forged = deepcopy(payload)
        forged["decision"][field] = value
        with pytest.raises(ValidationError):
            InstallationRecord.model_validate(forged)

    rejected = deepcopy(payload)
    rejected["decision"]["decision"] = "rejected"
    rejected["decision"]["reason"] = "not approved"
    with pytest.raises(ValidationError, match="inconsistent with current state"):
        InstallationRecord.model_validate(rejected)

    missing_submitted_event = deepcopy(payload)
    missing_submitted_event["decision"]["submittedRevision"] = 1
    with pytest.raises(ValidationError, match="submitted event"):
        InstallationRecord.model_validate(missing_submitted_event)

    stale_tail = deepcopy(payload)
    stale_tail["events"][-1]["toState"] = "rejected"
    with pytest.raises(ValidationError, match="event tail must match"):
        InstallationRecord.model_validate(stale_tail)

    state_jump = deepcopy(payload)
    state_jump["state"] = "applied"
    state_jump["current"]["state"] = "applied"
    state_jump["events"][-1]["toState"] = "applied"
    with pytest.raises(ValidationError, match="invalid state transition"):
        InstallationRecord.model_validate(state_jump)


def test_all_frozen_resource_limit_constants_are_exact() -> None:
    assert MAX_REQUESTED_BUNDLES == 64
    assert MAX_SNAPSHOT_CANDIDATES == 4096
    assert MAX_RESOLVED_NODES == 512
    assert MAX_DEPENDENCY_EDGES == 4096
    assert MAX_DEPENDENCY_DEPTH == 64
    assert MAX_BACKTRACKING_STATES == 10000
    assert MAX_CONTRIBUTION_CLAIMS == 10000
    assert MAX_CANONICAL_LOCK_PAYLOAD_BYTES == 4 * 1024 * 1024
