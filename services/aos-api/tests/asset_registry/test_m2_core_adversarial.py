"""Independent adversarial checks for the M2-A1 resolver boundary."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionRequest,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
)
from aos_api.asset_registry.errors import AssetRegistryError, AssetRegistryErrorCode
from aos_api.asset_registry.resolver import resolve

CHECKED_AT = datetime(2026, 8, 3, tzinfo=UTC)


def _digest(label: str) -> str:
    return canonical_sha256({"w4": label})


def _candidate(
    coordinate: tuple[str, str, str],
    *,
    required: tuple[tuple[str | None, str, str], ...] = (),
    optional: tuple[tuple[str | None, str, str], ...] = (),
    conflicts: tuple[tuple[str | None, str, str | None], ...] = (),
    provides: tuple[str, ...] = (),
    requires: tuple[str, ...] = (),
    contributions: tuple[dict[str, str], ...] = (),
) -> RegistrySnapshotCandidate:
    publisher, bundle_id, version = coordinate

    def dependency_manifest(
        dependencies: tuple[tuple[str | None, str, str], ...],
    ) -> list[dict[str, str]]:
        return [
            {
                **({"publisher": owner} if owner is not None else {}),
                "id": dependency_id,
                "version": requirement,
            }
            for owner, dependency_id, requirement in dependencies
        ]

    manifest_conflicts = [
        {
            **({"publisher": owner} if owner is not None else {}),
            "id": conflict_id,
            **({"version": requirement} if requirement is not None else {}),
        }
        for owner, conflict_id, requirement in conflicts
    ]
    manifest = {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": bundle_id,
            "version": version,
            "displayName": f"W4 {bundle_id}",
            "publisher": publisher,
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.0.0 <2.0.0",
            "dependencies": dependency_manifest(required),
            "optionalDependencies": dependency_manifest(optional),
            "conflicts": manifest_conflicts,
            "exports": {},
            "capabilities": {
                "provides": list(provides),
                "requires": list(requires),
            },
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {
                "plan": None,
                "downgradePolicy": "retain-canonical",
            },
            "preflight": None,
            "regression": None,
            "rollback": None,
            "contributions": list(contributions),
        },
    }
    return RegistrySnapshotCandidate.model_validate(
        {
            "publisher": publisher,
            "id": bundle_id,
            "version": version,
            "kind": "SolutionPack",
            "manifest": manifest,
            "contentHash": _digest(f"content:{publisher}:{bundle_id}:{version}"),
            "signatureFingerprint": _digest(
                f"signature:{publisher}:{bundle_id}:{version}"
            ),
            "releaseEvidenceRevision": _digest(
                f"evidence:{publisher}:{bundle_id}:{version}"
            ),
            "dependencies": [
                {
                    "publisher": owner or publisher,
                    "id": dependency_id,
                    "version": requirement,
                }
                for owner, dependency_id, requirement in required
            ],
            "optionalDependencies": [
                {
                    "publisher": owner or publisher,
                    "id": dependency_id,
                    "version": requirement,
                }
                for owner, dependency_id, requirement in optional
            ],
            "conflicts": [
                {
                    "publisher": owner or publisher,
                    "id": conflict_id,
                    "version": requirement,
                }
                for owner, conflict_id, requirement in conflicts
            ],
            "capabilities": {
                "provides": list(provides),
                "requires": list(requires),
            },
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migration": {
                "planRef": None,
                "downgradePolicy": "retain-canonical",
            },
            "contributions": list(contributions),
        }
    )


def _snapshot(*candidates: RegistrySnapshotCandidate) -> RegistrySnapshot:
    return RegistrySnapshot.build(
        candidates=list(candidates),
        checked_at=CHECKED_AT,
    )


def _request(
    *requested: tuple[str, str, str],
    snapshot: RegistrySnapshot,
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
            "registrySnapshotHash": snapshot.snapshot_hash,
            "currentInstallationRef": None,
        }
    )


def test_publisher_is_exact_and_prerelease_requires_an_explicit_constraint() -> None:
    snapshot = _snapshot(
        _candidate(("partner", "solution.shared", "9.0.0")),
        _candidate(("aos", "solution.shared", "1.0.0")),
        _candidate(("aos", "solution.shared", "2.0.0-beta.1")),
    )

    stable = resolve(
        _request(
            ("aos", "solution.shared", ">=1.0.0 <3.0.0"),
            snapshot=snapshot,
        ),
        snapshot,
        None,
    )
    prerelease = resolve(
        _request(
            ("aos", "solution.shared", "2.0.0-beta.1"),
            snapshot=snapshot,
        ),
        snapshot,
        None,
    )

    assert [(item.publisher, item.version) for item in stable.resolved] == [
        ("aos", "1.0.0")
    ]
    assert [(item.publisher, item.version) for item in prerelease.resolved] == [
        ("aos", "2.0.0-beta.1")
    ]


def test_optional_dependency_activates_only_when_top_level_requested() -> None:
    root = _candidate(
        ("aos", "solution.root", "1.0.0"),
        optional=((None, "plugin.search", "^1.0.0"),),
    )
    plugin = _candidate(("aos", "plugin.search", "1.2.0"))
    snapshot = _snapshot(root, plugin)

    without_optional = resolve(
        _request(("aos", "solution.root", "1.0.0"), snapshot=snapshot),
        snapshot,
        None,
    )
    with_optional = resolve(
        _request(
            ("aos", "solution.root", "1.0.0"),
            ("aos", "plugin.search", "^1.0.0"),
            snapshot=snapshot,
        ),
        snapshot,
        None,
    )

    assert [item.id for item in without_optional.resolved] == ["solution.root"]
    assert {item.id for item in with_optional.resolved} == {
        "solution.root",
        "plugin.search",
    }
    assert len(with_optional.edges) == 1
    assert with_optional.edges[0].optional is True


def test_invalid_highest_version_backtracks_to_a_lower_valid_graph() -> None:
    addon = _candidate(("aos", "plugin.addon", "1.0.0"))
    high = _candidate(
        ("aos", "solution.fallback", "2.0.0"),
        conflicts=((None, "plugin.addon", None),),
    )
    low = _candidate(("aos", "solution.fallback", "1.0.0"))
    snapshot = _snapshot(addon, high, low)

    lock = resolve(
        _request(
            ("aos", "solution.fallback", ">=1.0.0 <3.0.0"),
            ("aos", "plugin.addon", "1.0.0"),
            snapshot=snapshot,
        ),
        snapshot,
        None,
    )

    selected = {(item.id, item.version) for item in lock.resolved}
    assert selected == {("solution.fallback", "1.0.0"), ("plugin.addon", "1.0.0")}


def test_cycle_and_explicit_conflict_return_structured_errors() -> None:
    cycle_snapshot = _snapshot(
        _candidate(
            ("aos", "solution.a", "1.0.0"),
            required=((None, "solution.b", "1.0.0"),),
        ),
        _candidate(
            ("aos", "solution.b", "1.0.0"),
            required=((None, "solution.a", "1.0.0"),),
        ),
    )
    with pytest.raises(AssetRegistryError) as cycle:
        resolve(
            _request(("aos", "solution.a", "1.0.0"), snapshot=cycle_snapshot),
            cycle_snapshot,
            None,
        )
    assert cycle.value.code == AssetRegistryErrorCode.DEPENDENCY_CYCLE
    assert cycle.value.details is not None
    assert [item["id"] for item in cycle.value.details["cycle"]] == [
        "solution.a",
        "solution.b",
    ]

    conflict_snapshot = _snapshot(
        _candidate(
            ("aos", "solution.a", "1.0.0"),
            conflicts=((None, "solution.b", None),),
        ),
        _candidate(("aos", "solution.b", "1.0.0")),
    )
    with pytest.raises(AssetRegistryError) as conflict:
        resolve(
            _request(
                ("aos", "solution.a", "1.0.0"),
                ("aos", "solution.b", "1.0.0"),
                snapshot=conflict_snapshot,
            ),
            conflict_snapshot,
            None,
        )
    assert conflict.value.code == AssetRegistryErrorCode.DEPENDENCY_CONFLICT
    assert conflict.value.details is not None
    assert conflict.value.details["subtype"] == "explicit_conflict"


@pytest.mark.parametrize("provider_count", [0, 2])
def test_capability_requires_exactly_one_selected_provider(provider_count: int) -> None:
    candidates = [
        _candidate(
            ("aos", "solution.consumer", "1.0.0"),
            requires=("cap.orders",),
        )
    ]
    requested = [("aos", "solution.consumer", "1.0.0")]
    for index in range(provider_count):
        bundle_id = f"plugin.provider-{index}"
        candidates.append(
            _candidate(
                ("aos", bundle_id, "1.0.0"),
                provides=("cap.orders",),
            )
        )
        requested.append(("aos", bundle_id, "1.0.0"))
    snapshot = _snapshot(*candidates)

    with pytest.raises(AssetRegistryError) as caught:
        resolve(_request(*requested, snapshot=snapshot), snapshot, None)

    assert caught.value.code == AssetRegistryErrorCode.DEPENDENCY_CONFLICT
    assert caught.value.details is not None
    assert caught.value.details["subtype"] == (
        "capability_missing" if provider_count == 0 else "capability_multiple"
    )


def test_normalized_api_contribution_collision_is_not_bypassed_by_parameter_name() -> (
    None
):
    left_claim = {
        "kind": "api",
        "method": "GET",
        "path": "/orders/{id}",
        "operationId": "getOrderLeft",
        "mode": "exclusive",
    }
    right_claim = {
        "kind": "api",
        "method": "GET",
        "path": "/orders/{orderId}",
        "operationId": "getOrderRight",
        "mode": "exclusive",
    }
    snapshot = _snapshot(
        _candidate(
            ("aos", "plugin.left", "1.0.0"),
            contributions=(left_claim,),
        ),
        _candidate(
            ("aos", "plugin.right", "1.0.0"),
            contributions=(right_claim,),
        ),
    )

    with pytest.raises(AssetRegistryError) as caught:
        resolve(
            _request(
                ("aos", "plugin.left", "1.0.0"),
                ("aos", "plugin.right", "1.0.0"),
                snapshot=snapshot,
            ),
            snapshot,
            None,
        )

    assert caught.value.code == AssetRegistryErrorCode.DEPENDENCY_CONFLICT
    assert caught.value.details is not None
    assert caught.value.details["subtype"] == "contribution_collision"
    assert caught.value.details["resource"]["kind"] == "api"


def test_real_resolved_node_count_fails_at_max_plus_one() -> None:
    direct_dependencies = tuple(
        (None, f"node-{index:03d}", "1.0.0") for index in range(500)
    )
    extra_dependencies = tuple(
        (None, f"extra-{index:03d}", "1.0.0") for index in range(12)
    )
    candidates = [
        _candidate(
            ("aos", "solution.budget-root", "1.0.0"),
            required=direct_dependencies,
        )
    ]
    candidates.extend(
        _candidate(
            ("aos", f"node-{index:03d}", "1.0.0"),
            required=extra_dependencies if index == 0 else (),
        )
        for index in range(500)
    )
    candidates.extend(
        _candidate(("aos", f"extra-{index:03d}", "1.0.0")) for index in range(12)
    )
    snapshot = _snapshot(*candidates)

    with pytest.raises(AssetRegistryError) as caught:
        resolve(
            _request(
                ("aos", "solution.budget-root", "1.0.0"),
                snapshot=snapshot,
            ),
            snapshot,
            None,
        )

    assert caught.value.code == AssetRegistryErrorCode.RESOLUTION_LIMIT_EXCEEDED
    assert caught.value.details == {
        "resource": "resolved_nodes",
        "limit": 512,
        "observed": 513,
    }
