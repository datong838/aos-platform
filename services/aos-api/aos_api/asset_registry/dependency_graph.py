"""Pure deterministic dependency selection for composition resolution."""

from __future__ import annotations

import heapq
from collections.abc import Callable
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Literal

from semantic_version import Version

from aos_api.asset_registry.composition_contracts import (
    MAX_BACKTRACKING_STATES,
    MAX_CANONICAL_LOCK_PAYLOAD_BYTES,
    MAX_CONTRIBUTION_CLAIMS,
    MAX_DEPENDENCY_DEPTH,
    MAX_DEPENDENCY_EDGES,
    MAX_REQUESTED_BUNDLES,
    MAX_RESOLVED_NODES,
    MAX_SNAPSHOT_CANDIDATES,
    CandidateRejection,
    CompositionRequest,
    ConstraintPathNode,
    ConstraintRecord,
    DependencyConflictDetails,
    DependencyCycleDetails,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
    ResolutionLimitDetails,
    ResolvedBundle,
    ResolvedEdge,
    resolved_edge_sort_key,
)
from aos_api.asset_registry.errors import (
    AssetRegistryError,
    DependencyConflictError,
    DependencyCycleError,
    ResolutionLimitExceededError,
)
from aos_api.asset_registry.semver import parse_range, parse_version

Coordinate = tuple[str, str]
Via = Literal["requested", "dependency", "optional"]

RESOURCE_LIMITS: dict[str, int] = {
    "requested": MAX_REQUESTED_BUNDLES,
    "snapshot_candidates": MAX_SNAPSHOT_CANDIDATES,
    "resolved_nodes": MAX_RESOLVED_NODES,
    "dependency_edges": MAX_DEPENDENCY_EDGES,
    "dependency_depth": MAX_DEPENDENCY_DEPTH,
    "backtracking_states": MAX_BACKTRACKING_STATES,
    "contribution_claims": MAX_CONTRIBUTION_CLAIMS,
    "canonical_lock_payload_bytes": MAX_CANONICAL_LOCK_PAYLOAD_BYTES,
}


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    """Resolved public DTOs produced by the deterministic graph search."""

    resolved: tuple[ResolvedBundle, ...]
    edges: tuple[ResolvedEdge, ...]


@dataclass(slots=True)
class _SearchBudget:
    backtracking_states: int = 0

    def record_candidate_attempt(self) -> None:
        self.backtracking_states += 1
        enforce_resolution_limit(
            "backtracking_states",
            self.backtracking_states,
        )


def enforce_resolution_limit(resource: str, observed: int) -> None:
    """Fail with the frozen structured error when a deterministic budget is exceeded."""

    limit = RESOURCE_LIMITS[resource]
    if observed <= limit:
        return
    details = ResolutionLimitDetails.model_validate(
        {"resource": resource, "limit": limit, "observed": observed}
    )
    raise ResolutionLimitExceededError(
        "deterministic resolution resource limit exceeded",
        details=details.model_dump(mode="json", by_alias=True),
    )


def resolve_dependency_graph(
    request: CompositionRequest,
    snapshot: RegistrySnapshot,
    *,
    validate_complete: Callable[[tuple[ResolvedBundle, ...]], None] | None = None,
) -> DependencyGraph:
    """Resolve a request against exactly one immutable snapshot."""

    enforce_resolution_limit("requested", len(request.requested))
    enforce_resolution_limit("snapshot_candidates", len(snapshot.candidates))

    candidates_by_coordinate: dict[Coordinate, list[RegistrySnapshotCandidate]] = {}
    for candidate in snapshot.candidates:
        candidates_by_coordinate.setdefault(
            (candidate.publisher, candidate.id), []
        ).append(candidate)
    for candidates in candidates_by_coordinate.values():
        candidates.sort(key=cmp_to_key(_compare_candidates))

    top_level = {(item.publisher, item.id) for item in request.requested}
    root_constraints = tuple(
        ConstraintRecord.model_validate(
            {
                "sourcePublisher": item.publisher,
                "sourceId": item.id,
                "sourceVersion": None,
                "targetPublisher": item.publisher,
                "targetId": item.id,
                "requirement": item.version,
                "optional": False,
            }
        )
        for item in request.requested
    )
    selected = _search(
        request=request,
        candidates_by_coordinate=candidates_by_coordinate,
        top_level=top_level,
        root_constraints=root_constraints,
        selected={},
        budget=_SearchBudget(),
        validate_complete=validate_complete,
    )
    edges = _build_edges(selected, top_level)
    _raise_for_cycle_or_depth(selected, edges, top_level)
    resolved = tuple(
        _to_resolved_bundle(
            candidate,
            selection_reason=(
                "requested"
                if (candidate.publisher, candidate.id) in top_level
                else "dependency"
            ),
        )
        for _, candidate in sorted(selected.items())
    )
    return DependencyGraph(resolved=resolved, edges=tuple(edges))


def _search(
    *,
    request: CompositionRequest,
    candidates_by_coordinate: dict[Coordinate, list[RegistrySnapshotCandidate]],
    top_level: set[Coordinate],
    root_constraints: tuple[ConstraintRecord, ...],
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    budget: _SearchBudget,
    validate_complete: Callable[[tuple[ResolvedBundle, ...]], None] | None,
) -> dict[Coordinate, RegistrySnapshotCandidate]:
    constraints, active = _derive_constraints(
        root_constraints=root_constraints,
        selected=selected,
        top_level=top_level,
    )
    enforce_resolution_limit("resolved_nodes", len(active))
    _raise_if_selected_candidates_are_invalid(
        request=request,
        selected=selected,
        constraints=constraints,
        candidates_by_coordinate=candidates_by_coordinate,
        top_level=top_level,
    )

    unresolved = sorted(active - selected.keys())
    if not unresolved:
        edges = _build_edges(selected, top_level)
        _raise_for_cycle_or_depth(selected, edges, top_level)
        if validate_complete is not None:
            validate_complete(_resolved_bundles(selected, top_level))
        return selected

    coordinate = unresolved[0]
    options, rejections = _candidate_options(
        request=request,
        coordinate=coordinate,
        constraints=constraints[coordinate],
        candidates=candidates_by_coordinate.get(coordinate, []),
    )
    if not options:
        _raise_coordinate_conflict(
            coordinate=coordinate,
            constraints=constraints,
            candidates_by_coordinate=candidates_by_coordinate,
            selected=selected,
            top_level=top_level,
            candidate_rejections=rejections,
        )

    first_failure: AssetRegistryError | None = None
    for candidate in options:
        budget.record_candidate_attempt()
        branch = dict(selected)
        branch[coordinate] = candidate
        try:
            return _search(
                request=request,
                candidates_by_coordinate=candidates_by_coordinate,
                top_level=top_level,
                root_constraints=root_constraints,
                selected=branch,
                budget=budget,
                validate_complete=validate_complete,
            )
        except (DependencyConflictError, DependencyCycleError) as exc:
            if first_failure is None:
                first_failure = exc
    if first_failure is not None:
        raise first_failure
    raise AssertionError("candidate search exhausted without a stable failure")


def _derive_constraints(
    *,
    root_constraints: tuple[ConstraintRecord, ...],
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    top_level: set[Coordinate],
) -> tuple[dict[Coordinate, list[ConstraintRecord]], set[Coordinate]]:
    constraints: dict[Coordinate, list[ConstraintRecord]] = {}
    active: set[Coordinate] = set(top_level)
    for record in root_constraints:
        coordinate = (record.target_publisher, record.target_id)
        constraints.setdefault(coordinate, []).append(record)

    edge_count = 0
    for source_coordinate, source in sorted(selected.items()):
        dependencies = [(item, False) for item in source.dependencies]
        dependencies.extend(
            (item, True)
            for item in source.optional_dependencies
            if (item.publisher, item.id) in top_level
        )
        for dependency, optional in dependencies:
            edge_count += 1
            target = (dependency.publisher, dependency.id)
            active.add(target)
            constraints.setdefault(target, []).append(
                ConstraintRecord.model_validate(
                    {
                        "sourcePublisher": source_coordinate[0],
                        "sourceId": source_coordinate[1],
                        "sourceVersion": source.version,
                        "targetPublisher": target[0],
                        "targetId": target[1],
                        "requirement": dependency.version,
                        "optional": optional,
                    }
                )
            )
    enforce_resolution_limit("dependency_edges", edge_count)
    for records in constraints.values():
        records.sort(key=_constraint_sort_key)
    return constraints, active


def _raise_if_selected_candidates_are_invalid(
    *,
    request: CompositionRequest,
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    constraints: dict[Coordinate, list[ConstraintRecord]],
    candidates_by_coordinate: dict[Coordinate, list[RegistrySnapshotCandidate]],
    top_level: set[Coordinate],
) -> None:
    for coordinate, candidate in sorted(selected.items()):
        reason = _candidate_rejection_reason(
            request=request,
            candidate=candidate,
            constraints=constraints[coordinate],
        )
        if reason is None:
            continue
        _, rejections = _candidate_options(
            request=request,
            coordinate=coordinate,
            constraints=constraints[coordinate],
            candidates=candidates_by_coordinate.get(coordinate, []),
        )
        _raise_coordinate_conflict(
            coordinate=coordinate,
            constraints=constraints,
            candidates_by_coordinate=candidates_by_coordinate,
            selected=selected,
            top_level=top_level,
            candidate_rejections=rejections,
        )


def _candidate_options(
    *,
    request: CompositionRequest,
    coordinate: Coordinate,
    constraints: list[ConstraintRecord],
    candidates: list[RegistrySnapshotCandidate],
) -> tuple[list[RegistrySnapshotCandidate], list[CandidateRejection]]:
    accepted: list[RegistrySnapshotCandidate] = []
    rejected: list[CandidateRejection] = []
    for candidate in candidates:
        reason = _candidate_rejection_reason(
            request=request,
            candidate=candidate,
            constraints=constraints,
        )
        if reason is None:
            accepted.append(candidate)
        else:
            rejected.append(
                CandidateRejection.model_validate(
                    {
                        "publisher": coordinate[0],
                        "id": coordinate[1],
                        "version": candidate.version,
                        "reason": reason,
                    }
                )
            )
    return accepted, rejected


def _candidate_rejection_reason(
    *,
    request: CompositionRequest,
    candidate: RegistrySnapshotCandidate,
    constraints: list[ConstraintRecord],
) -> str | None:
    platform_requirement = candidate.manifest.spec.platform_api
    if not parse_range(platform_requirement).match(
        parse_version(request.platform_api_version)
    ):
        return "platform_api"
    version = parse_version(candidate.version)
    if version.prerelease and not any(
        _requirement_explicitly_mentions_prerelease(item.requirement)
        for item in constraints
    ):
        return "prerelease"
    if not all(parse_range(item.requirement).match(version) for item in constraints):
        return "version_constraint"
    return None


def _requirement_explicitly_mentions_prerelease(requirement: str) -> bool:
    for token in requirement.replace("||", " ").replace(",", " ").split():
        normalized = token.lstrip("<>=~^v")
        if "-" not in normalized:
            continue
        prefix = normalized.split("-", 1)[0]
        if prefix.count(".") == 2 and all(part.isdigit() for part in prefix.split(".")):
            return True
    return False


def _raise_coordinate_conflict(
    *,
    coordinate: Coordinate,
    constraints: dict[Coordinate, list[ConstraintRecord]],
    candidates_by_coordinate: dict[Coordinate, list[RegistrySnapshotCandidate]],
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    top_level: set[Coordinate],
    candidate_rejections: list[CandidateRejection],
) -> None:
    subtype = (
        "missing_dependency"
        if not candidates_by_coordinate.get(coordinate)
        else "version_intersection_empty"
    )
    details = DependencyConflictDetails.model_validate(
        {
            "subtype": subtype,
            "path": _stable_path(
                coordinate=coordinate,
                selected=selected,
                constraints=constraints,
                top_level=top_level,
            ),
            "constraints": constraints.get(coordinate, []),
            "candidateRejections": candidate_rejections,
            "resource": None,
        }
    )
    raise DependencyConflictError(
        "dependency resolution failed",
        details=details.model_dump(mode="json", by_alias=True, exclude_none=False),
    )


def _stable_path(
    *,
    coordinate: Coordinate,
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    constraints: dict[Coordinate, list[ConstraintRecord]],
    top_level: set[Coordinate],
) -> list[ConstraintPathNode]:
    adjacency: dict[Coordinate, list[tuple[Coordinate, Via]]] = {}
    for target, records in constraints.items():
        for record in records:
            source = (record.source_publisher, record.source_id)
            if record.source_version is None:
                continue
            adjacency.setdefault(source, []).append(
                (target, "optional" if record.optional else "dependency")
            )
    for values in adjacency.values():
        values.sort()

    paths: dict[Coordinate, tuple[Coordinate, ...]] = {}
    vias: dict[Coordinate, Via] = {root: "requested" for root in top_level}
    pending: list[tuple[int, tuple[Coordinate, ...], Coordinate, Via]] = [
        (1, (root,), root, "requested") for root in sorted(top_level)
    ]
    heapq.heapify(pending)
    while pending:
        _, path, source, entered_via = heapq.heappop(pending)
        current = paths.get(source)
        if current is not None and (len(current), current) <= (len(path), path):
            continue
        paths[source] = path
        vias[source] = entered_via
        for target, via in adjacency.get(source, []):
            if target in path:
                continue
            candidate_path = (*path, target)
            current_target = paths.get(target)
            if current_target is not None and (
                len(current_target),
                current_target,
            ) <= (len(candidate_path), candidate_path):
                continue
            heapq.heappush(
                pending,
                (len(candidate_path), candidate_path, target, via),
            )
    coordinates = paths.get(coordinate, (coordinate,))
    nodes: list[ConstraintPathNode] = []
    for index, item in enumerate(coordinates):
        candidate = selected.get(item)
        nodes.append(
            ConstraintPathNode.model_validate(
                {
                    "publisher": item[0],
                    "id": item[1],
                    "version": candidate.version if candidate is not None else None,
                    "via": "requested" if index == 0 else vias[item],
                }
            )
        )
    return nodes


def _build_edges(
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    top_level: set[Coordinate],
) -> list[ResolvedEdge]:
    edges: list[ResolvedEdge] = []
    for source_coordinate, source in sorted(selected.items()):
        dependencies = [(item, False) for item in source.dependencies]
        dependencies.extend(
            (item, True)
            for item in source.optional_dependencies
            if (item.publisher, item.id) in top_level
        )
        for dependency, optional in dependencies:
            target = selected[(dependency.publisher, dependency.id)]
            edges.append(
                ResolvedEdge.model_validate(
                    {
                        "fromPublisher": source_coordinate[0],
                        "fromId": source_coordinate[1],
                        "fromVersion": source.version,
                        "toPublisher": target.publisher,
                        "toId": target.id,
                        "toVersion": target.version,
                        "constraint": dependency.version,
                        "optional": optional,
                    }
                )
            )
    enforce_resolution_limit("dependency_edges", len(edges))
    return sorted(edges, key=resolved_edge_sort_key)


def _raise_for_cycle_or_depth(
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    edges: list[ResolvedEdge],
    top_level: set[Coordinate],
) -> None:
    adjacency: dict[Coordinate, list[tuple[Coordinate, Via]]] = {
        coordinate: [] for coordinate in selected
    }
    for edge in edges:
        source = (edge.from_publisher, edge.from_id)
        target = (edge.to_publisher, edge.to_id)
        adjacency[source].append(
            (target, "optional" if edge.optional else "dependency")
        )
    for targets in adjacency.values():
        targets.sort()

    state: dict[Coordinate, int] = {}
    stack: list[Coordinate] = []
    entered_via: dict[Coordinate, Via] = {
        coordinate: "requested" for coordinate in top_level
    }

    def visit(node: Coordinate) -> int:
        state[node] = 1
        stack.append(node)
        longest = 1
        for target, via in adjacency[node]:
            if state.get(target) == 1:
                start = stack.index(target)
                cycle_coordinates = stack[start:]
                cycle = [
                    ConstraintPathNode.model_validate(
                        {
                            "publisher": coordinate[0],
                            "id": coordinate[1],
                            "version": selected[coordinate].version,
                            "via": (
                                via
                                if coordinate == target
                                else entered_via.get(coordinate, "dependency")
                            ),
                        }
                    )
                    for coordinate in cycle_coordinates
                ]
                details = DependencyCycleDetails.model_validate({"cycle": cycle})
                raise DependencyCycleError(
                    "dependency cycle detected",
                    details=details.model_dump(mode="json", by_alias=True),
                )
            if state.get(target) != 2:
                entered_via[target] = via
                target_depth = visit(target)
            else:
                target_depth = depths[target]
            longest = max(longest, 1 + target_depth)
        stack.pop()
        state[node] = 2
        depths[node] = longest
        return longest

    depths: dict[Coordinate, int] = {}
    maximum_depth = 0
    for coordinate in sorted(selected):
        if state.get(coordinate) != 2:
            maximum_depth = max(maximum_depth, visit(coordinate))
    enforce_resolution_limit("dependency_depth", maximum_depth)


def _to_resolved_bundle(
    candidate: RegistrySnapshotCandidate,
    *,
    selection_reason: Literal["requested", "dependency"],
) -> ResolvedBundle:
    return ResolvedBundle.model_validate(
        {
            "publisher": candidate.publisher,
            "id": candidate.id,
            "version": candidate.version,
            "kind": candidate.kind,
            "contentHash": candidate.content_hash,
            "signatureFingerprint": candidate.signature_fingerprint,
            "releaseEvidenceRevision": candidate.release_evidence_revision,
            "dependencies": candidate.dependencies,
            "optionalDependencies": candidate.optional_dependencies,
            "conflicts": candidate.conflicts,
            "capabilities": candidate.capabilities,
            "permissions": candidate.permissions,
            "migration": candidate.migration,
            "contributions": candidate.contributions,
            "selectionReason": selection_reason,
        }
    )


def _resolved_bundles(
    selected: dict[Coordinate, RegistrySnapshotCandidate],
    top_level: set[Coordinate],
) -> tuple[ResolvedBundle, ...]:
    return tuple(
        _to_resolved_bundle(
            candidate,
            selection_reason=("requested" if coordinate in top_level else "dependency"),
        )
        for coordinate, candidate in sorted(selected.items())
    )


def _compare_candidates(
    left: RegistrySnapshotCandidate,
    right: RegistrySnapshotCandidate,
) -> int:
    left_version = parse_version(left.version)
    right_version = parse_version(right.version)
    precedence = _compare_version_precedence(left_version, right_version)
    if precedence:
        return -precedence
    left_key = (left.version, left.publisher, left.id, left.content_hash)
    right_key = (right.version, right.publisher, right.id, right.content_hash)
    return (left_key > right_key) - (left_key < right_key)


def _compare_version_precedence(left: Version, right: Version) -> int:
    return (left > right) - (left < right)


def _constraint_sort_key(record: ConstraintRecord) -> tuple[object, ...]:
    return (
        record.target_publisher,
        record.target_id,
        record.source_publisher,
        record.source_id,
        record.source_version or "",
        record.requirement,
        record.optional,
    )
