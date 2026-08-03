"""Pure deterministic composition resolver and lock payload builder."""

from __future__ import annotations

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
    DependencyConflictDetails,
    RegistrySnapshot,
    ResolvedBundle,
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

    graph = resolve_dependency_graph(
        request,
        snapshot,
        validate_complete=_validate_complete_graph,
    )
    resolved = list(graph.resolved)
    _raise_for_explicit_conflicts(resolved)
    providers = _resolve_capability_providers(resolved)
    _raise_for_contribution_collisions(resolved)

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


def _raise_for_explicit_conflicts(resolved: list[ResolvedBundle]) -> None:
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
            )


def _validate_complete_graph(resolved: tuple[ResolvedBundle, ...]) -> None:
    bundles = list(resolved)
    _raise_for_explicit_conflicts(bundles)
    _resolve_capability_providers(bundles)
    _raise_for_contribution_collisions(bundles)


def _resolve_capability_providers(
    resolved: list[ResolvedBundle],
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


def _raise_for_contribution_collisions(resolved: list[ResolvedBundle]) -> None:
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
        )


def _raise_resource_conflict(
    *,
    subtype: str,
    kind: str,
    key: str,
    owners: list[ResolvedBundle],
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
            "path": [],
            "constraints": [],
            "candidateRejections": [],
            "resource": resource,
        }
    )
    raise DependencyConflictError(
        "resolved composition contains a resource conflict",
        details=details.model_dump(mode="json", by_alias=True, exclude_none=False),
    )


def _bundle_sort_key(bundle: ResolvedBundle) -> tuple[object, ...]:
    return (
        bundle.publisher,
        bundle.id,
        parse_version(bundle.version),
        bundle.version,
        bundle.content_hash,
    )
