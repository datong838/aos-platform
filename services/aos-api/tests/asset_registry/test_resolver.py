"""End-to-end pure resolver tests for conflicts, lock payloads, and determinism."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
)
from aos_api.asset_registry.errors import (
    CurrentInstallationStaleError,
    DependencyConflictError,
    RegistrySnapshotStaleError,
)
from aos_api.asset_registry.resolver import resolve

CHECKED_AT = datetime(2026, 8, 3, tzinfo=UTC)


def _sha(label: str) -> str:
    return canonical_sha256(label)


def _request(
    *requested: tuple[str, str, str],
    snapshot_hash: str | None = None,
    with_current_ref: bool = False,
) -> CompositionRequest:
    return CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": publisher, "id": bundle_id, "version": version}
                for publisher, bundle_id, version in requested
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": snapshot_hash,
            "currentInstallationRef": (
                {
                    "installationId": "11111111-1111-4111-8111-111111111111",
                    "revision": 3,
                    "lockHash": _sha("old-lock"),
                    "overlayRevision": "overlay-v3",
                }
                if with_current_ref
                else None
            ),
        }
    )


def _candidate(
    bundle_id: str,
    version: str,
    *,
    publisher: str = "aos",
    dependencies: list[tuple[str | None, str, str]] | None = None,
    optional_dependencies: list[tuple[str | None, str, str]] | None = None,
    conflicts: list[tuple[str | None, str, str | None]] | None = None,
    provides: list[str] | None = None,
    requires: list[str] | None = None,
    roles: list[str] | None = None,
    plan_ref: str | None = None,
    contributions: list[dict] | None = None,
) -> RegistrySnapshotCandidate:
    dependencies = dependencies or []
    optional_dependencies = optional_dependencies or []
    conflicts = conflicts or []
    provides = provides or []
    requires = requires or []
    roles = roles or []
    contributions = contributions or []

    def dependency_payload(
        values: list[tuple[str | None, str, str]],
    ) -> list[dict]:
        return [
            {"publisher": item_publisher, "id": item_id, "version": requirement}
            if item_publisher is not None
            else {"id": item_id, "version": requirement}
            for item_publisher, item_id, requirement in values
        ]

    manifest_conflicts = [
        {
            **({"publisher": item_publisher} if item_publisher is not None else {}),
            "id": item_id,
            **({"version": requirement} if requirement is not None else {}),
        }
        for item_publisher, item_id, requirement in conflicts
    ]
    manifest = {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": bundle_id,
            "version": version,
            "displayName": bundle_id,
            "publisher": publisher,
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.0.0 <2.0.0",
            "dependencies": dependency_payload(dependencies),
            "optionalDependencies": dependency_payload(optional_dependencies),
            "conflicts": manifest_conflicts,
            "exports": {},
            "capabilities": {"provides": provides, "requires": requires},
            "permissions": {
                "roles": roles,
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {
                "plan": plan_ref,
                "downgradePolicy": "retain-canonical",
            },
            "preflight": None,
            "regression": None,
            "rollback": None,
            "contributions": contributions,
        },
    }
    return RegistrySnapshotCandidate.model_validate(
        {
            "publisher": publisher,
            "id": bundle_id,
            "version": version,
            "kind": "SolutionPack",
            "manifest": manifest,
            "contentHash": _sha(f"content:{publisher}:{bundle_id}:{version}"),
            "signatureFingerprint": _sha(
                f"signature:{publisher}:{bundle_id}:{version}"
            ),
            "releaseEvidenceRevision": _sha(
                f"evidence:{publisher}:{bundle_id}:{version}"
            ),
            "dependencies": [
                {
                    "publisher": item_publisher or publisher,
                    "id": item_id,
                    "version": requirement,
                }
                for item_publisher, item_id, requirement in dependencies
            ],
            "optionalDependencies": [
                {
                    "publisher": item_publisher or publisher,
                    "id": item_id,
                    "version": requirement,
                }
                for item_publisher, item_id, requirement in optional_dependencies
            ],
            "conflicts": [
                {
                    "publisher": item_publisher or publisher,
                    "id": item_id,
                    "version": requirement,
                }
                for item_publisher, item_id, requirement in conflicts
            ],
            "capabilities": {"provides": provides, "requires": requires},
            "permissions": {
                "roles": roles,
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migration": {
                "planRef": plan_ref,
                "downgradePolicy": "retain-canonical",
            },
            "contributions": contributions,
        }
    )


def _snapshot(
    candidates: list[RegistrySnapshotCandidate],
    *,
    checked_at: datetime = CHECKED_AT,
) -> RegistrySnapshot:
    return RegistrySnapshot.build(candidates=candidates, checked_at=checked_at)


def test_resolve_builds_exact_lock_payload_without_identity_or_time() -> None:
    snapshot = _snapshot(
        [
            _candidate(
                "pack.root",
                "1.0.0",
                dependencies=[(None, "pack.provider", "^1.0.0")],
                requires=["orders.read"],
                roles=["reader"],
                plan_ref="migrations/root.json",
            ),
            _candidate(
                "pack.provider",
                "1.2.0",
                provides=["orders.read"],
            ),
        ]
    )
    request = _request(
        ("aos", "pack.root", "1.0.0"), snapshot_hash=snapshot.snapshot_hash
    )

    payload = resolve(request, snapshot, None)

    assert isinstance(payload, CompositionLockPayload)
    assert [item.id for item in payload.resolved] == ["pack.provider", "pack.root"]
    assert payload.resolved[0].selection_reason == "dependency"
    assert payload.resolved[1].selection_reason == "requested"
    assert payload.capability_providers[0].capability == "orders.read"
    assert payload.permission_diff.target.roles == ["reader"]
    assert payload.migration_plan.target[0].id == "pack.root"
    dumped = payload.model_dump(mode="json", by_alias=True, exclude_none=False)
    assert "compositionId" not in dumped
    assert "createdAt" not in dumped
    assert canonical_sha256(payload.hash_payload_dump()) == canonical_sha256(dumped)


def test_resolver_backtracks_from_highest_candidate_with_missing_dependency() -> None:
    snapshot = _snapshot(
        [
            _candidate(
                "pack.root",
                "2.0.0",
                dependencies=[(None, "pack.missing", "1.0.0")],
            ),
            _candidate("pack.root", "1.0.0"),
        ]
    )

    payload = resolve(_request(("aos", "pack.root", "*")), snapshot, None)

    assert payload.resolved[0].version == "1.0.0"


def test_snapshot_and_current_installation_preconditions_fail_closed() -> None:
    snapshot = _snapshot([_candidate("pack.root", "1.0.0")])

    with pytest.raises(RegistrySnapshotStaleError):
        resolve(
            _request(("aos", "pack.root", "1.0.0"), snapshot_hash=_sha("stale")),
            snapshot,
            None,
        )
    with pytest.raises(CurrentInstallationStaleError):
        resolve(
            _request(("aos", "pack.root", "1.0.0"), with_current_ref=True),
            snapshot,
            None,
        )
    with pytest.raises(CurrentInstallationStaleError):
        resolve(
            _request(("aos", "pack.root", "1.0.0")),
            snapshot,
            CompositionLockPayload.model_construct(resolved=[]),
        )


def test_explicit_bundle_conflict_has_sorted_owner_resource() -> None:
    snapshot = _snapshot(
        [
            _candidate(
                "pack.a",
                "1.0.0",
                conflicts=[(None, "pack.b", "^1.0.0")],
            ),
            _candidate("pack.b", "1.2.0"),
        ]
    )

    with pytest.raises(DependencyConflictError) as raised:
        resolve(
            _request(
                ("aos", "pack.a", "1.0.0"),
                ("aos", "pack.b", "1.2.0"),
            ),
            snapshot,
            None,
        )

    assert raised.value.details["subtype"] == "explicit_conflict"
    assert raised.value.details["resource"]["kind"] == "bundle"
    assert [item["id"] for item in raised.value.details["resource"]["owners"]] == [
        "pack.a",
        "pack.b",
    ]


def test_highest_explicit_conflict_backtracks_to_lower_valid_version() -> None:
    snapshot = _snapshot(
        [
            _candidate(
                "pack.a",
                "2.0.0",
                conflicts=[(None, "pack.b", None)],
            ),
            _candidate("pack.a", "1.0.0"),
            _candidate("pack.b", "1.0.0"),
        ]
    )

    payload = resolve(
        _request(("aos", "pack.a", "*"), ("aos", "pack.b", "1.0.0")),
        snapshot,
        None,
    )

    assert next(item for item in payload.resolved if item.id == "pack.a").version == (
        "1.0.0"
    )


def test_capability_requires_exactly_one_selected_provider() -> None:
    requester = _candidate("pack.requester", "1.0.0", requires=["orders.read"])
    provider_a = _candidate("pack.provider-a", "1.0.0", provides=["orders.read"])
    provider_b = _candidate("pack.provider-b", "1.0.0", provides=["orders.read"])

    with pytest.raises(DependencyConflictError) as missing:
        resolve(
            _request(("aos", "pack.requester", "1.0.0")),
            _snapshot([requester]),
            None,
        )
    assert missing.value.details["subtype"] == "capability_missing"

    with pytest.raises(DependencyConflictError) as multiple:
        resolve(
            _request(
                ("aos", "pack.requester", "1.0.0"),
                ("aos", "pack.provider-a", "1.0.0"),
                ("aos", "pack.provider-b", "1.0.0"),
            ),
            _snapshot([requester, provider_b, provider_a]),
            None,
        )
    assert multiple.value.details["subtype"] == "capability_multiple"
    assert [item["id"] for item in multiple.value.details["resource"]["owners"]] == [
        "pack.provider-a",
        "pack.provider-b",
    ]


def test_highest_capability_conflict_backtracks_to_lower_valid_version() -> None:
    snapshot = _snapshot(
        [
            _candidate("pack.root", "2.0.0", requires=["orders.write"]),
            _candidate("pack.root", "1.0.0"),
        ]
    )

    payload = resolve(_request(("aos", "pack.root", "*")), snapshot, None)

    assert payload.resolved[0].version == "1.0.0"


def test_contribution_collision_uses_normalized_key_and_shared_claims_can_coexist() -> (
    None
):
    first = _candidate(
        "pack.first",
        "1.0.0",
        contributions=[
            {
                "kind": "navigation",
                "route": "/Orders/:orderId",
                "mode": "exclusive",
            }
        ],
    )
    second = _candidate(
        "pack.second",
        "1.0.0",
        contributions=[
            {
                "kind": "navigation",
                "route": "/orders/:id/",
                "mode": "shared",
            }
        ],
    )
    with pytest.raises(DependencyConflictError) as raised:
        resolve(
            _request(
                ("aos", "pack.first", "1.0.0"),
                ("aos", "pack.second", "1.0.0"),
            ),
            _snapshot([second, first]),
            None,
        )
    assert raised.value.details["subtype"] == "contribution_collision"
    assert raised.value.details["resource"]["key"] == '["/orders/:"]'

    shared_first = _candidate(
        "pack.shared-a",
        "1.0.0",
        contributions=[
            {
                "kind": "ui",
                "slot": "order.detail.actions",
                "id": "retry",
                "mode": "shared",
            }
        ],
    )
    shared_second = _candidate(
        "pack.shared-b",
        "1.0.0",
        contributions=[
            {
                "kind": "ui",
                "slot": "order.detail.actions",
                "id": "retry",
                "mode": "shared",
            }
        ],
    )
    payload = resolve(
        _request(
            ("aos", "pack.shared-a", "1.0.0"),
            ("aos", "pack.shared-b", "1.0.0"),
        ),
        _snapshot([shared_second, shared_first]),
        None,
    )
    assert len(payload.contribution_diff.added) == 2


@pytest.mark.parametrize(
    ("first_claim", "second_claim", "expected_kind", "expected_key"),
    [
        (
            {
                "kind": "api",
                "method": "GET",
                "path": "/v1/orders/{id}",
                "operationId": "getOrderA",
                "mode": "exclusive",
            },
            {
                "kind": "api",
                "method": "GET",
                "path": "/v1/orders/{orderId}/",
                "operationId": "getOrderB",
                "mode": "exclusive",
            },
            "api",
            '["GET","/v1/orders/{}"]',
        ),
        (
            {
                "kind": "api",
                "method": "POST",
                "path": "/v1/orders:retry",
                "operationId": "retryOrder",
                "mode": "exclusive",
            },
            {
                "kind": "api",
                "method": "POST",
                "path": "/v1/archive:retry",
                "operationId": "retryOrder",
                "mode": "exclusive",
            },
            "api-operation",
            '["retryOrder"]',
        ),
    ],
)
def test_api_path_and_operation_id_conflicts_are_both_enforced(
    first_claim: dict,
    second_claim: dict,
    expected_kind: str,
    expected_key: str,
) -> None:
    first = _candidate("pack.api-a", "1.0.0", contributions=[first_claim])
    second = _candidate("pack.api-b", "1.0.0", contributions=[second_claim])

    with pytest.raises(DependencyConflictError) as raised:
        resolve(
            _request(
                ("aos", "pack.api-a", "1.0.0"),
                ("aos", "pack.api-b", "1.0.0"),
            ),
            _snapshot([second, first]),
            None,
        )

    assert raised.value.details["resource"]["kind"] == expected_kind
    assert raised.value.details["resource"]["key"] == expected_key


def test_highest_contribution_collision_backtracks_to_lower_valid_version() -> None:
    collision = {
        "kind": "navigation",
        "route": "/orders/:id",
        "mode": "exclusive",
    }
    snapshot = _snapshot(
        [
            _candidate("pack.a", "2.0.0", contributions=[collision]),
            _candidate("pack.a", "1.0.0"),
            _candidate("pack.b", "1.0.0", contributions=[collision]),
        ]
    )

    payload = resolve(
        _request(("aos", "pack.a", "*"), ("aos", "pack.b", "1.0.0")),
        snapshot,
        None,
    )

    assert next(item for item in payload.resolved if item.id == "pack.a").version == (
        "1.0.0"
    )


def test_verified_baseline_drives_lock_diffs_and_current_ref() -> None:
    old_snapshot = _snapshot([_candidate("pack.root", "1.0.0", roles=["reader"])])
    old_payload = resolve(_request(("aos", "pack.root", "1.0.0")), old_snapshot, None)
    new_snapshot = _snapshot([_candidate("pack.root", "2.0.0", roles=["writer"])])

    new_payload = resolve(
        _request(("aos", "pack.root", "2.0.0"), with_current_ref=True),
        new_snapshot,
        old_payload,
    )

    assert new_payload.current_installation_ref is not None
    assert new_payload.current_installation_ref.revision == 3
    assert new_payload.permission_diff.baseline.roles == ["reader"]
    assert new_payload.permission_diff.target.roles == ["writer"]
    assert new_payload.permission_diff.added.roles == ["writer"]
    assert new_payload.permission_diff.removed.roles == ["reader"]


def test_one_hundred_fixed_seed_permutations_keep_payload_and_hash_identical() -> None:
    candidates = [
        _candidate(
            "pack.root",
            "1.0.0",
            dependencies=[(None, "pack.shared", "^1.0.0")],
            requires=["orders.read"],
        ),
        _candidate("pack.root", "1.1.0"),
        _candidate("pack.shared", "1.0.0", provides=["orders.read"]),
        _candidate("pack.shared", "1.5.0", provides=["orders.read"]),
        _candidate("pack.extra", "1.0.0"),
    ]
    requested = [
        ("aos", "pack.root", "1.0.0"),
        ("aos", "pack.extra", "1.0.0"),
    ]
    expected_bytes: bytes | None = None
    expected_hash: str | None = None

    for seed in range(100):
        rng = random.Random(seed)
        shuffled_candidates = list(candidates)
        shuffled_requested = list(requested)
        rng.shuffle(shuffled_candidates)
        rng.shuffle(shuffled_requested)
        snapshot = _snapshot(
            shuffled_candidates,
            checked_at=CHECKED_AT + timedelta(seconds=seed),
        )
        payload = resolve(_request(*shuffled_requested), snapshot, None)
        payload_bytes = canonical_json(payload.hash_payload_dump())
        payload_hash = canonical_sha256(payload.hash_payload_dump())
        if expected_bytes is None:
            expected_bytes = payload_bytes
            expected_hash = payload_hash
        assert payload_bytes == expected_bytes, f"seed={seed}"
        assert payload_hash == expected_hash, f"seed={seed}"
