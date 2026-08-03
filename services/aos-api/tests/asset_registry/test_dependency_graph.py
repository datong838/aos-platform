"""Tests for deterministic dependency graph selection and diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionRequest,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
)
from aos_api.asset_registry.dependency_graph import (
    RESOURCE_LIMITS,
    enforce_resolution_limit,
    resolve_dependency_graph,
)
from aos_api.asset_registry.errors import (
    DependencyConflictError,
    DependencyCycleError,
    ResolutionLimitExceededError,
)

CHECKED_AT = datetime(2026, 8, 3, tzinfo=UTC)


def _sha(label: str) -> str:
    return canonical_sha256(label)


def _request(*requested: tuple[str, str, str]) -> CompositionRequest:
    return CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": publisher, "id": bundle_id, "version": version}
                for publisher, bundle_id, version in requested
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": None,
            "currentInstallationRef": None,
        }
    )


def _candidate(
    bundle_id: str,
    version: str,
    *,
    publisher: str = "aos",
    dependencies: list[tuple[str | None, str, str]] | None = None,
    optional_dependencies: list[tuple[str | None, str, str]] | None = None,
    platform_api: str = ">=1.0.0 <2.0.0",
) -> RegistrySnapshotCandidate:
    dependencies = dependencies or []
    optional_dependencies = optional_dependencies or []
    manifest_dependencies = [
        {"publisher": dep_publisher, "id": dep_id, "version": requirement}
        if dep_publisher is not None
        else {"id": dep_id, "version": requirement}
        for dep_publisher, dep_id, requirement in dependencies
    ]
    manifest_optional = [
        {"publisher": dep_publisher, "id": dep_id, "version": requirement}
        if dep_publisher is not None
        else {"id": dep_id, "version": requirement}
        for dep_publisher, dep_id, requirement in optional_dependencies
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
            "platformApi": platform_api,
            "dependencies": manifest_dependencies,
            "optionalDependencies": manifest_optional,
            "conflicts": [],
            "exports": {},
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {"plan": None, "downgradePolicy": "retain-canonical"},
            "preflight": None,
            "regression": None,
            "rollback": None,
            "contributions": [],
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
                    "publisher": dep_publisher or publisher,
                    "id": dep_id,
                    "version": requirement,
                }
                for dep_publisher, dep_id, requirement in dependencies
            ],
            "optionalDependencies": [
                {
                    "publisher": dep_publisher or publisher,
                    "id": dep_id,
                    "version": requirement,
                }
                for dep_publisher, dep_id, requirement in optional_dependencies
            ],
            "conflicts": [],
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migration": {"planRef": None, "downgradePolicy": "retain-canonical"},
            "contributions": [],
        }
    )


def _snapshot(*candidates: RegistrySnapshotCandidate) -> RegistrySnapshot:
    return RegistrySnapshot.build(candidates=list(candidates), checked_at=CHECKED_AT)


def test_exact_and_range_choose_deterministic_highest_stable_version() -> None:
    snapshot = _snapshot(
        _candidate("pack.root", "1.0.0"),
        _candidate("pack.root", "1.5.0"),
        _candidate("pack.root", "2.0.0"),
    )

    exact = resolve_dependency_graph(_request(("aos", "pack.root", "1.0.0")), snapshot)
    ranged = resolve_dependency_graph(
        _request(("aos", "pack.root", "^1.0.0")), snapshot
    )

    assert [item.version for item in exact.resolved] == ["1.0.0"]
    assert [item.version for item in ranged.resolved] == ["1.5.0"]


def test_prerelease_requires_an_explicit_prerelease_constraint() -> None:
    snapshot = _snapshot(
        _candidate("pack.root", "1.9.0"),
        _candidate("pack.root", "2.0.0-alpha.2"),
    )

    stable = resolve_dependency_graph(
        _request(("aos", "pack.root", ">=1.0.0")), snapshot
    )
    prerelease = resolve_dependency_graph(
        _request(("aos", "pack.root", ">=2.0.0-alpha.1 <2.0.0")), snapshot
    )

    assert stable.resolved[0].version == "1.9.0"
    assert prerelease.resolved[0].version == "2.0.0-alpha.2"


def test_same_id_from_different_publishers_never_uses_an_implicit_default() -> None:
    snapshot = _snapshot(
        _candidate("pack.root", "1.0.0", publisher="zeta"),
        _candidate("pack.root", "2.0.0", publisher="aos"),
    )

    graph = resolve_dependency_graph(_request(("zeta", "pack.root", "*")), snapshot)

    assert [(item.publisher, item.version) for item in graph.resolved] == [
        ("zeta", "1.0.0")
    ]


def test_platform_api_filter_is_applied_before_version_selection() -> None:
    snapshot = _snapshot(
        _candidate("pack.root", "2.0.0", platform_api=">=2.0.0"),
        _candidate("pack.root", "1.0.0", platform_api="^1.7.0"),
    )

    graph = resolve_dependency_graph(_request(("aos", "pack.root", "*")), snapshot)

    assert graph.resolved[0].version == "1.0.0"


def test_optional_dependency_is_enabled_only_by_top_level_request() -> None:
    root = _candidate(
        "pack.root",
        "1.0.0",
        optional_dependencies=[(None, "pack.optional", "^1.0.0")],
    )
    optional = _candidate("pack.optional", "1.2.0")
    snapshot = _snapshot(root, optional)

    disabled = resolve_dependency_graph(
        _request(("aos", "pack.root", "1.0.0")), snapshot
    )
    enabled = resolve_dependency_graph(
        _request(
            ("aos", "pack.root", "1.0.0"),
            ("aos", "pack.optional", "^1.0.0"),
        ),
        snapshot,
    )

    assert [item.id for item in disabled.resolved] == ["pack.root"]
    assert [item.id for item in enabled.resolved] == ["pack.optional", "pack.root"]
    assert len(enabled.edges) == 1
    assert enabled.edges[0].optional is True


def test_required_dependency_does_not_indirectly_activate_optional_dependency() -> None:
    root = _candidate(
        "pack.root",
        "1.0.0",
        dependencies=[(None, "pack.required", "1.0.0")],
        optional_dependencies=[(None, "pack.optional", "1.0.0")],
    )
    graph = resolve_dependency_graph(
        _request(("aos", "pack.root", "1.0.0")),
        _snapshot(
            root,
            _candidate("pack.required", "1.0.0"),
            _candidate("pack.optional", "1.0.0"),
        ),
    )

    assert [item.id for item in graph.resolved] == ["pack.required", "pack.root"]
    assert all(not edge.optional for edge in graph.edges)


def test_missing_dependency_has_stable_structured_path() -> None:
    root = _candidate(
        "pack.root",
        "1.0.0",
        dependencies=[(None, "pack.missing", "^1.0.0")],
    )

    with pytest.raises(DependencyConflictError) as raised:
        resolve_dependency_graph(
            _request(("aos", "pack.root", "1.0.0")), _snapshot(root)
        )

    assert raised.value.details["subtype"] == "missing_dependency"
    assert raised.value.details["path"] == [
        {
            "publisher": "aos",
            "id": "pack.root",
            "version": "1.0.0",
            "via": "requested",
        },
        {
            "publisher": "aos",
            "id": "pack.missing",
            "version": None,
            "via": "dependency",
        },
    ]


def test_diamond_dependencies_intersect_all_constraints() -> None:
    snapshot = _snapshot(
        _candidate(
            "pack.left",
            "1.0.0",
            dependencies=[(None, "pack.shared", ">=1.0.0 <3.0.0")],
        ),
        _candidate(
            "pack.right",
            "1.0.0",
            dependencies=[(None, "pack.shared", ">=2.0.0 <4.0.0")],
        ),
        _candidate("pack.shared", "1.5.0"),
        _candidate("pack.shared", "2.5.0"),
        _candidate("pack.shared", "3.5.0"),
    )
    graph = resolve_dependency_graph(
        _request(
            ("aos", "pack.left", "1.0.0"),
            ("aos", "pack.right", "1.0.0"),
        ),
        snapshot,
    )

    shared = next(item for item in graph.resolved if item.id == "pack.shared")
    assert shared.version == "2.5.0"
    assert len(graph.edges) == 2


def test_empty_version_intersection_is_stable() -> None:
    snapshot = _snapshot(
        _candidate(
            "pack.left",
            "1.0.0",
            dependencies=[(None, "pack.shared", "^1.0.0")],
        ),
        _candidate(
            "pack.right",
            "1.0.0",
            dependencies=[(None, "pack.shared", "^2.0.0")],
        ),
        _candidate("pack.shared", "1.5.0"),
        _candidate("pack.shared", "2.5.0"),
    )

    with pytest.raises(DependencyConflictError) as raised:
        resolve_dependency_graph(
            _request(
                ("aos", "pack.left", "1.0.0"),
                ("aos", "pack.right", "1.0.0"),
            ),
            snapshot,
        )

    assert raised.value.details["subtype"] == "version_intersection_empty"
    assert [item["requirement"] for item in raised.value.details["constraints"]] == [
        "^1.0.0",
        "^2.0.0",
    ]


def test_cycle_is_rotated_to_the_smallest_coordinate_without_reversing_edges() -> None:
    snapshot = _snapshot(
        _candidate(
            "pack.b",
            "1.0.0",
            dependencies=[(None, "pack.a", "1.0.0")],
        ),
        _candidate(
            "pack.a",
            "1.0.0",
            dependencies=[(None, "pack.b", "1.0.0")],
        ),
    )

    with pytest.raises(DependencyCycleError) as raised:
        resolve_dependency_graph(_request(("aos", "pack.b", "1.0.0")), snapshot)

    assert [item["id"] for item in raised.value.details["cycle"]] == [
        "pack.a",
        "pack.b",
    ]


def test_cycle_in_highest_version_backtracks_to_lower_acyclic_version() -> None:
    snapshot = _snapshot(
        _candidate(
            "pack.root",
            "2.0.0",
            dependencies=[(None, "pack.child", "2.0.0")],
        ),
        _candidate("pack.root", "1.0.0"),
        _candidate(
            "pack.child",
            "2.0.0",
            dependencies=[(None, "pack.root", "2.0.0")],
        ),
    )

    graph = resolve_dependency_graph(_request(("aos", "pack.root", "*")), snapshot)

    assert [(item.id, item.version) for item in graph.resolved] == [
        ("pack.root", "1.0.0")
    ]


@pytest.mark.parametrize("resource,limit", sorted(RESOURCE_LIMITS.items()))
def test_every_resolution_budget_accepts_max_minus_one_and_max_then_rejects_max_plus_one(
    resource: str,
    limit: int,
) -> None:
    enforce_resolution_limit(resource, limit - 1)
    enforce_resolution_limit(resource, limit)

    with pytest.raises(ResolutionLimitExceededError) as raised:
        enforce_resolution_limit(resource, limit + 1)

    assert raised.value.details == {
        "resource": resource,
        "limit": limit,
        "observed": limit + 1,
    }
