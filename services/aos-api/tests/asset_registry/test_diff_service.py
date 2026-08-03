"""Tests for the three exact deterministic composition diffs."""

from __future__ import annotations

from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    ResolvedBundle,
)
from aos_api.asset_registry.diff_service import (
    build_contribution_diff,
    build_migration_plan_diff,
    build_permission_diff,
)

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def _resolved(
    bundle_id: str,
    version: str,
    *,
    roles: list[str] | None = None,
    markings: list[str] | None = None,
    data_scopes: list[str] | None = None,
    action_types: list[str] | None = None,
    plan_ref: str | None = None,
    contributions: list[dict] | None = None,
) -> ResolvedBundle:
    return ResolvedBundle.model_validate(
        {
            "publisher": "aos",
            "id": bundle_id,
            "version": version,
            "kind": "SolutionPack",
            "contentHash": SHA_A,
            "signatureFingerprint": SHA_B,
            "releaseEvidenceRevision": SHA_C,
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": roles or [],
                "markings": markings or [],
                "dataScopes": data_scopes or [],
                "actionTypes": action_types or [],
            },
            "migration": {
                "planRef": plan_ref,
                "downgradePolicy": "retain-canonical",
            },
            "contributions": contributions or [],
            "selectionReason": "requested",
        }
    )


def _baseline(*resolved: ResolvedBundle) -> CompositionLockPayload:
    return CompositionLockPayload.model_construct(resolved=list(resolved))


def test_permission_diff_uses_full_union_and_exact_set_operations() -> None:
    baseline = _baseline(
        _resolved(
            "pack.old",
            "1.0.0",
            roles=["reader", "shared"],
            markings=["internal"],
            data_scopes=["orders.read"],
            action_types=["view"],
        )
    )
    target = [
        _resolved(
            "pack.new",
            "2.0.0",
            roles=["shared", "writer"],
            markings=["restricted"],
            data_scopes=["orders.read", "orders.write"],
            action_types=["edit"],
        )
    ]

    diff = build_permission_diff(target, baseline)

    assert diff.baseline.roles == ["reader", "shared"]
    assert diff.target.roles == ["shared", "writer"]
    assert diff.added.roles == ["writer"]
    assert diff.removed.roles == ["reader"]
    assert diff.unchanged.roles == ["shared"]
    assert diff.added.markings == ["restricted"]
    assert diff.removed.action_types == ["view"]
    assert diff.unchanged.data_scopes == ["orders.read"]


def test_permission_diff_without_baseline_uses_four_explicit_empty_sets() -> None:
    diff = build_permission_diff(
        [_resolved("pack.new", "1.0.0", roles=["reader"])], None
    )

    assert diff.baseline.model_dump(mode="json", by_alias=True) == {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    assert diff.added == diff.target
    assert all(
        not getattr(diff.removed, field)
        for field in ("roles", "markings", "data_scopes", "action_types")
    )


def test_migration_diff_preserves_owner_and_distinguishes_changed_steps() -> None:
    baseline = _baseline(
        _resolved("pack.changed", "1.0.0", plan_ref="migrations/v1.json"),
        _resolved("pack.removed", "1.0.0", plan_ref="migrations/remove.json"),
        _resolved("pack.no-plan", "1.0.0"),
    )
    target = [
        _resolved("pack.changed", "2.0.0", plan_ref="migrations/v2.json"),
        _resolved("pack.added", "1.0.0", plan_ref="migrations/add.json"),
    ]

    diff = build_migration_plan_diff(target, baseline)

    assert [item.id for item in diff.baseline] == ["pack.changed", "pack.removed"]
    assert [item.id for item in diff.target] == ["pack.added", "pack.changed"]
    assert [item.id for item in diff.added] == ["pack.added"]
    assert [item.id for item in diff.removed] == ["pack.removed"]
    assert len(diff.changed) == 1
    assert diff.changed[0].id == "pack.changed"
    assert diff.changed[0].before.version == "1.0.0"
    assert diff.changed[0].after.version == "2.0.0"


def test_contribution_diff_keeps_owner_coordinate_for_identical_claims() -> None:
    shared_claim = {
        "kind": "ui",
        "slot": "order.detail.actions",
        "id": "retry",
        "mode": "shared",
    }
    removed_claim = {
        "kind": "navigation",
        "route": "/legacy/:id",
        "mode": "exclusive",
    }
    added_claim = {
        "kind": "navigation",
        "route": "/orders/:id",
        "mode": "exclusive",
    }
    baseline = _baseline(
        _resolved("pack.same", "1.0.0", contributions=[shared_claim]),
        _resolved("pack.removed", "1.0.0", contributions=[removed_claim]),
    )
    target = [
        _resolved("pack.same", "1.0.0", contributions=[shared_claim]),
        _resolved("pack.other-owner", "1.0.0", contributions=[shared_claim]),
        _resolved("pack.added", "1.0.0", contributions=[added_claim]),
    ]

    diff = build_contribution_diff(target, baseline)

    assert [(item.id, item.claim.kind) for item in diff.unchanged] == [
        ("pack.same", "ui")
    ]
    assert {(item.id, item.claim.kind) for item in diff.added} == {
        ("pack.added", "navigation"),
        ("pack.other-owner", "ui"),
    }
    assert [(item.id, item.claim.kind) for item in diff.removed] == [
        ("pack.removed", "navigation")
    ]
