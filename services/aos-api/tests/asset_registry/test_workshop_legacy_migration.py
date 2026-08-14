"""W1-B L1 conservation proof for W01/W02/W03 Workshop migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.ecommerce_workshop_migration import (
    EcommerceWorkshopMigrationError,
    validate_ecommerce_workshop_legacy_migration,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
BUNDLES_ROOT = REPO_ROOT / "bundles"


def _loaded_solution_packs():
    loader = ManifestLoader({"m5-fixtures": BUNDLES_ROOT})
    return (
        loader.load("bundle://m5-fixtures/solutions/ecommerce-operations-base"),
        loader.load("bundle://m5-fixtures/solutions/ecommerce-growth"),
    )


def test_w01_w02_w03_migration_conserves_every_widget_object_and_source_ref() -> None:
    results = validate_ecommerce_workshop_legacy_migration(_loaded_solution_packs())

    assert [item.source_id for item in results] == [
        "w01-order-management",
        "w02-product-inventory",
        "w03-customer-private-domain",
    ]
    assert [item.target_module_id for item in results] == [
        "ecommerce.operations",
        "ecommerce.operations",
        "ecommerce.customer",
    ]
    assert all(item.missing_widget_ids == () for item in results)
    assert all(item.missing_object_ids == () for item in results)
    assert all(item.source_ref_preserved for item in results)
    assert all(item.legacy_route_preserved for item in results)
    assert sum(len(item.mapped_widgets) for item in results) == 14


def test_unknown_or_missing_legacy_source_fails_closed() -> None:
    operations, growth = _loaded_solution_packs()
    mutated = growth.model_copy(
        update={"legacy_workshops": growth.legacy_workshops[:-1]}
    )

    with pytest.raises(EcommerceWorkshopMigrationError, match="legacy source set"):
        validate_ecommerce_workshop_legacy_migration((operations, mutated))
