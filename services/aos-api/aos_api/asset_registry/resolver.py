"""Pure deterministic composition resolver and lock payload builder."""

from __future__ import annotations

import heapq
from collections import defaultdict

from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.composition_contracts import (
    LOCK_SCHEMA_VERSION,
    RESOLVER_VERSION,
    CapabilityProvider,
    CompositionLockPayload,
    CompositionRequest,
    ConflictOwner,
    ConflictResource,
    ConstraintPathNode,
    DependencyConflictDetails,
    RegistrySnapshot,
    ResolvedBundle,
    ResolvedEdge,
)
from aos_api.asset_registry.contracts import contribution_conflict_keys
from aos_api.asset_registry.dependency_graph import (
    enforce_resolution_limit,
    resolve_dependency_graph,
)
from aos_api.asset_registry.diff_service import (
    build_contribution_diff,
    build_migration_plan_diff,
    build_permission_diff,
)
from aos_api.asset_registry.errors import (
    CurrentInstallationStaleError,
    DependencyConflictError,
    RegistrySnapshotStaleError,
)
from aos_api.asset_registry.semver import parse_range, parse_version

Coordinate = tuple[str, str]
PathKey = tuple[tuple[str, str, str, str], ...]


def resolve(
    request: CompositionRequest,
    snapshot: RegistrySnapshot,
    baseline: CompositionLockPayload | None,
) -> CompositionLockPayload:
    """Resolve without database, network, environment, identity, or time access."""

    if (
        request.registry_snapshot_hash is not None
        and request.registry_snapshot_hash != snapshot.snapshot_hash
    ):
        raise RegistrySnapshotStaleError(
            "registry snapshot precondition is stale",
            details={
                "expected": request.registry_snapshot_hash,
                "actual": snapshot.snapshot_hash,
            },
        )
    if (request.current_installation_ref is None) != (baseline is None):
        raise CurrentInstallationStaleError(
            "current installation baseline is stale",
            details={"baselinePresent": baseline is not None},
        )

    roots = frozenset((item.publisher, item.id) for item in request.requested)

    def validate_complete(
        resolved: tuple[ResolvedBundle, ...],
        edges: tuple[ResolvedEdge, ...],
    ) -> None:
        _validate_complete_graph(resolved, edges, roots)

    graph = resolve_dependency_graph(
        request,
        snapshot,
        validate_complete=validate_complete,
    )
    resolved = list(graph.resolved)
    _raise_for_explicit_conflicts(resolved, graph.edges, roots)
    providers = _resolve_capability_providers(resolved, graph.edges, roots)
    _raise_for_contribution_collisions(resolved, graph.edges, roots)

    permission_diff = build_permission_diff(resolved, baseline)
    migration_plan = build_migration_plan_diff(resolved, baseline)
    contribution_diff = build_contribution_diff(resolved, baseline)
    payload = {
        "lockSchemaVersion": LOCK_SCHEMA_VERSION,
        "resolverVersion": RESOLVER_VERSION,
        "request": request.lock_request().model_dump(
            mode="json", by_alias=True, exclude_none=False
        ),
        "registrySnapshotHash": snapshot.snapshot_hash,
        "resolved": [
            item.model_dump(mode="json", by_alias=True, exclude_none=False)
            for item in resolved
        ],
        "edges": [
            item.model_dump(mode="json", by_alias=True, exclude_none=False)
            for item in graph.edges
        ],
        "capabilityProviders": [
            item.model_dump(mode="json", by_alias=True, exclude_none=False)
            for item in providers
        ],
        "permissionDiff": permission_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        ),
        "migrationPlan": migration_plan.model_dump(
            mode="json", by_alias=True, exclude_none=False
        ),
        "contributionDiff": contribution_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        ),
        "currentInstallationRef": (
            request.current_installation_ref.model_dump(
                mode="json", by_alias=True, exclude_none=False
            )
            if request.current_installation_ref is not None
            else None
        ),
    }
    payload_bytes = len(canonical_json(payload))
    enforce_resolution_limit("canonical_lock_payload_bytes", payload_bytes)
    return CompositionLockPayload.model_validate(payload)


def _raise_for_explicit_conflicts(
    resolved: list[ResolvedBundle],
    edges: tuple[ResolvedEdge, ...],
    roots: frozenset[Coordinate],
) -> None:
    by_coordinate = {(item.publisher, item.id): item for item in resolved}
    for source in sorted(resolved, key=_bundle_sort_key):
        for conflict in source.conflicts:
            target = by_coordinate.get((conflict.publisher, conflict.id))
            if target is None:
                continue
            if conflict.version is not None and not parse_range(conflict.version).match(
                parse_version(target.version)
            ):
                continue
            _raise_resource_conflict(
                subtype="explicit_conflict",
                kind="bundle",
                key=f"{target.publisher}/{target.id}",
                owners=[source, target],
                resolved=resolved,
                edges=edges,
                roots=roots,
            )


def _validate_complete_graph(
    resolved: tuple[ResolvedBundle, ...],
    edges: tuple[ResolvedEdge, ...],
    roots: frozenset[Coordinate],
) -> None:
    bundles = list(resolved)
    _raise_for_explicit_conflicts(bundles, edges, roots)
    _resolve_capability_providers(bundles, edges, roots)
    _raise_for_contribution_collisions(bundles, edges, roots)


def _resolve_capability_providers(
    resolved: list[ResolvedBundle],
    edges: tuple[ResolvedEdge, ...],
    roots: frozenset[Coordinate],
) -> list[CapabilityProvider]:
    provided: dict[str, list[ResolvedBundle]] = defaultdict(list)
    required: set[str] = set()
    for bundle in resolved:
        required.update(bundle.capabilities.requires)
        for capability in bundle.capabilities.provides:
            provided[capability].append(bundle)

    providers: list[CapabilityProvider] = []
    for capability in sorted(required):
        owners = sorted(provided.get(capability, []), key=_bundle_sort_key)
        if len(owners) != 1:
            _raise_resource_conflict(
                subtype=("capability_missing" if not owners else "capability_multiple"),
                kind="capability",
                key=capability,
                owners=owners
                or [
                    bundle
                    for bundle in sorted(resolved, key=_bundle_sort_key)
                    if capability in bundle.capabilities.requires
                ],
                resolved=resolved,
                edges=edges,
                roots=roots,
            )
        owner = owners[0]
        providers.append(
            CapabilityProvider.model_validate(
                {
                    "capability": capability,
                    "publisher": owner.publisher,
                    "id": owner.id,
                    "version": owner.version,
                }
            )
        )
    return providers


def _raise_for_contribution_collisions(
    resolved: list[ResolvedBundle],
    edges: tuple[ResolvedEdge, ...],
    roots: frozenset[Coordinate],
) -> None:
    claims: dict[tuple[str, ...], list[tuple[ResolvedBundle, str]]] = defaultdict(list)
    claim_count = 0
    for bundle in sorted(resolved, key=_bundle_sort_key):
        for claim in bundle.contributions:
            claim_count += 1
            enforce_resolution_limit("contribution_claims", claim_count)
            for key in contribution_conflict_keys(claim):
                claims[key].append((bundle, claim.mode))

    for key in sorted(claims):
        bindings = claims[key]
        if len(bindings) < 2 or all(mode == "shared" for _, mode in bindings):
            continue
        _raise_resource_conflict(
            subtype="contribution_collision",
            kind=key[0],
            key=canonical_json(list(key[1:])).decode("utf-8"),
            owners=[bundle for bundle, _ in bindings],
            resolved=resolved,
            edges=edges,
            roots=roots,
        )


def _raise_resource_conflict(
    *,
    subtype: str,
    kind: str,
    key: str,
    owners: list[ResolvedBundle],
    resolved: list[ResolvedBundle],
    edges: tuple[ResolvedEdge, ...],
    roots: frozenset[Coordinate],
) -> None:
    unique_owners = {(item.publisher, item.id, item.version): item for item in owners}
    resource = ConflictResource.model_validate(
        {
            "kind": kind,
            "key": key,
            "owners": [
                ConflictOwner.model_validate(
                    {
                        "publisher": item.publisher,
                        "id": item.id,
                        "version": item.version,
                    }
                )
                for _, item in sorted(unique_owners.items())
            ],
        }
    )
    details = DependencyConflictDetails.model_validate(
        {
            "subtype": subtype,
            "path": _resource_conflict_path(
                resolved=resolved,
                edges=edges,
                roots=roots,
                owner_coordinates={
                    (item.publisher, item.id) for item in unique_owners.values()
                },
            ),
            "constraints": [],
            "candidateRejections": [],
            "resource": resource,
        }
    )
    raise DependencyConflictError(
        "resolved composition contains a resource conflict",
        details=details.model_dump(mode="json", by_alias=True, exclude_none=False),
    )


def _resource_conflict_path(
    *,
    resolved: list[ResolvedBundle],
    edges: tuple[ResolvedEdge, ...],
    roots: frozenset[Coordinate],
    owner_coordinates: set[Coordinate],
) -> list[ConstraintPathNode]:
    versions = {(item.publisher, item.id): item.version for item in resolved}
    adjacency: dict[Coordinate, list[tuple[Coordinate, str]]] = defaultdict(list)
    for edge in edges:
        source = (edge.from_publisher, edge.from_id)
        target = (edge.to_publisher, edge.to_id)
        adjacency[source].append(
            (target, "optional" if edge.optional else "dependency")
        )
    for targets in adjacency.values():
        targets.sort(
            key=lambda item: (
                item[0][0],
                item[0][1],
                versions[item[0]],
                item[1],
            )
        )

    pending: list[tuple[int, PathKey, Coordinate]] = []
    for root in sorted(roots):
        root_path = ((root[0], root[1], versions[root], "requested"),)
        heapq.heappush(pending, (1, root_path, root))

    best: dict[Coordinate, tuple[int, PathKey]] = {}
    while pending:
        length, path, coordinate = heapq.heappop(pending)
        current = best.get(coordinate)
        if current is not None and current <= (length, path):
            continue
        best[coordinate] = (length, path)
        if coordinate in owner_coordinates:
            return [
                ConstraintPathNode.model_validate(
                    {
                        "publisher": publisher,
                        "id": bundle_id,
                        "version": version,
                        "via": via,
                    }
                )
                for publisher, bundle_id, version, via in path
            ]
        path_coordinates = {(item[0], item[1]) for item in path}
        for target, via in adjacency.get(coordinate, []):
            if target in path_coordinates:
                continue
            target_path = (
                *path,
                (target[0], target[1], versions[target], via),
            )
            heapq.heappush(pending, (length + 1, target_path, target))

    raise AssertionError("resource conflict owner is unreachable from requested roots")


def _bundle_sort_key(bundle: ResolvedBundle) -> tuple[object, ...]:
    return (
        bundle.publisher,
        bundle.id,
        parse_version(bundle.version),
        bundle.version,
        bundle.content_hash,
    )
