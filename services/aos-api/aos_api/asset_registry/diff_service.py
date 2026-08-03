"""Pure deterministic composition diff construction."""

from __future__ import annotations

from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    ContributionBinding,
    ContributionDiff,
    MigrationChange,
    MigrationPlanDiff,
    MigrationStep,
    PermissionDiff,
    PermissionSet,
    ResolvedBundle,
    contribution_binding_sort_key,
    migration_step_sort_key,
)


def build_permission_diff(
    resolved: list[ResolvedBundle] | tuple[ResolvedBundle, ...],
    baseline: CompositionLockPayload | None,
) -> PermissionDiff:
    baseline_permissions = _aggregate_permissions(
        baseline.resolved if baseline is not None else []
    )
    target_permissions = _aggregate_permissions(resolved)
    return PermissionDiff.model_validate(
        {
            "baseline": baseline_permissions,
            "target": target_permissions,
            "added": _permission_operation(
                target_permissions, baseline_permissions, "-"
            ),
            "removed": _permission_operation(
                baseline_permissions, target_permissions, "-"
            ),
            "unchanged": _permission_operation(
                baseline_permissions, target_permissions, "&"
            ),
        }
    )


def build_migration_plan_diff(
    resolved: list[ResolvedBundle] | tuple[ResolvedBundle, ...],
    baseline: CompositionLockPayload | None,
) -> MigrationPlanDiff:
    baseline_steps = _migration_steps(baseline.resolved if baseline is not None else [])
    target_steps = _migration_steps(resolved)
    baseline_by_coordinate = {
        (item.publisher, item.id): item for item in baseline_steps
    }
    target_by_coordinate = {(item.publisher, item.id): item for item in target_steps}
    added = [
        target_by_coordinate[coordinate]
        for coordinate in target_by_coordinate.keys() - baseline_by_coordinate.keys()
    ]
    removed = [
        baseline_by_coordinate[coordinate]
        for coordinate in baseline_by_coordinate.keys() - target_by_coordinate.keys()
    ]
    changed = [
        MigrationChange.model_validate(
            {
                "publisher": coordinate[0],
                "id": coordinate[1],
                "before": baseline_by_coordinate[coordinate],
                "after": target_by_coordinate[coordinate],
            }
        )
        for coordinate in baseline_by_coordinate.keys() & target_by_coordinate.keys()
        if baseline_by_coordinate[coordinate] != target_by_coordinate[coordinate]
    ]
    return MigrationPlanDiff.model_validate(
        {
            "baseline": sorted(baseline_steps, key=migration_step_sort_key),
            "target": sorted(target_steps, key=migration_step_sort_key),
            "added": sorted(added, key=migration_step_sort_key),
            "removed": sorted(removed, key=migration_step_sort_key),
            "changed": sorted(changed, key=lambda item: (item.publisher, item.id)),
        }
    )


def build_contribution_diff(
    resolved: list[ResolvedBundle] | tuple[ResolvedBundle, ...],
    baseline: CompositionLockPayload | None,
) -> ContributionDiff:
    baseline_bindings = _contribution_bindings(
        baseline.resolved if baseline is not None else []
    )
    target_bindings = _contribution_bindings(resolved)
    baseline_by_identity = {_binding_identity(item): item for item in baseline_bindings}
    target_by_identity = {_binding_identity(item): item for item in target_bindings}
    return ContributionDiff.model_validate(
        {
            "baseline": baseline_bindings,
            "target": target_bindings,
            "added": [
                target_by_identity[key]
                for key in target_by_identity.keys() - baseline_by_identity.keys()
            ],
            "removed": [
                baseline_by_identity[key]
                for key in baseline_by_identity.keys() - target_by_identity.keys()
            ],
            "unchanged": [
                target_by_identity[key]
                for key in target_by_identity.keys() & baseline_by_identity.keys()
            ],
        }
    )


def _aggregate_permissions(
    resolved: list[ResolvedBundle] | tuple[ResolvedBundle, ...],
) -> PermissionSet:
    values = {
        "roles": set[str](),
        "markings": set[str](),
        "dataScopes": set[str](),
        "actionTypes": set[str](),
    }
    for bundle in resolved:
        values["roles"].update(bundle.permissions.roles)
        values["markings"].update(bundle.permissions.markings)
        values["dataScopes"].update(bundle.permissions.data_scopes)
        values["actionTypes"].update(bundle.permissions.action_types)
    return PermissionSet.model_validate(
        {field: sorted(items) for field, items in values.items()}
    )


def _permission_operation(
    left: PermissionSet,
    right: PermissionSet,
    operation: str,
) -> PermissionSet:
    result: dict[str, list[str]] = {}
    for field, attribute in (
        ("roles", "roles"),
        ("markings", "markings"),
        ("dataScopes", "data_scopes"),
        ("actionTypes", "action_types"),
    ):
        left_values = set(getattr(left, attribute))
        right_values = set(getattr(right, attribute))
        result[field] = sorted(
            left_values - right_values
            if operation == "-"
            else left_values & right_values
        )
    return PermissionSet.model_validate(result)


def _migration_steps(
    resolved: list[ResolvedBundle] | tuple[ResolvedBundle, ...],
) -> list[MigrationStep]:
    return sorted(
        [
            MigrationStep.model_validate(
                {
                    "publisher": bundle.publisher,
                    "id": bundle.id,
                    "version": bundle.version,
                    "planRef": bundle.migration.plan_ref,
                    "downgradePolicy": bundle.migration.downgrade_policy,
                }
            )
            for bundle in resolved
            if bundle.migration.plan_ref is not None
        ],
        key=migration_step_sort_key,
    )


def _contribution_bindings(
    resolved: list[ResolvedBundle] | tuple[ResolvedBundle, ...],
) -> list[ContributionBinding]:
    return sorted(
        [
            ContributionBinding.model_validate(
                {
                    "publisher": bundle.publisher,
                    "id": bundle.id,
                    "version": bundle.version,
                    "claim": claim,
                }
            )
            for bundle in resolved
            for claim in bundle.contributions
        ],
        key=contribution_binding_sort_key,
    )


def _binding_identity(binding: ContributionBinding) -> bytes:
    return canonical_json(
        binding.model_dump(mode="json", by_alias=True, exclude_none=False)
    )
