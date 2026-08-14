"""L1 ecommerce migration proof for the three frozen legacy Workshop assets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

from aos_api.asset_registry.contracts import LoadedBundle


class EcommerceWorkshopMigrationError(ValueError):
    """Raised when a legacy ecommerce Workshop cannot be conserved exactly."""


@dataclass(frozen=True, slots=True)
class LegacyWidgetMapping:
    source_widget_id: str
    target_view_id: str


@dataclass(frozen=True, slots=True)
class LegacyMigrationRule:
    source_id: str
    source_path: str
    target_module_id: str
    mapped_widgets: tuple[LegacyWidgetMapping, ...]


@dataclass(frozen=True, slots=True)
class LegacyMigrationValidation:
    source_id: str
    target_module_id: str
    mapped_widgets: tuple[LegacyWidgetMapping, ...]
    missing_widget_ids: tuple[str, ...]
    missing_object_ids: tuple[str, ...]
    source_ref_preserved: bool
    legacy_route_preserved: bool


ECOMMERCE_LEGACY_MIGRATION_RULES: Final = (
    LegacyMigrationRule(
        source_id="w01-order-management",
        source_path="content/workshops/w01-order-management.json",
        target_module_id="ecommerce.operations",
        mapped_widgets=(
            LegacyWidgetMapping("order-funnel", "orders.overview"),
            LegacyWidgetMapping("risky-orders", "orders.risk-queue"),
            LegacyWidgetMapping("sla-queue", "fulfillment.sla-queue"),
            LegacyWidgetMapping("order-sidebar", "orders.detail-drawer"),
        ),
    ),
    LegacyMigrationRule(
        source_id="w02-product-inventory",
        source_path="content/workshops/w02-product-inventory.json",
        target_module_id="ecommerce.operations",
        mapped_widgets=(
            LegacyWidgetMapping("product-sku-list", "product-inventory.catalog"),
            LegacyWidgetMapping("low-stock-queue", "product-inventory.low-stock"),
            LegacyWidgetMapping("category-tree", "product-inventory.categories"),
            LegacyWidgetMapping("quality-alert", "product-inventory.quality-alerts"),
        ),
    ),
    LegacyMigrationRule(
        source_id="w03-customer-private-domain",
        source_path="content/workshops/w03-customer-private-domain.json",
        target_module_id="ecommerce.customer",
        mapped_widgets=(
            LegacyWidgetMapping("customer-funnel", "segments.overview"),
            LegacyWidgetMapping("churn-high-risk", "segments.churn-risk"),
            LegacyWidgetMapping("vip-customer-list", "segments.vip"),
            LegacyWidgetMapping("dormant-customer-wakeup", "journeys.dormant"),
            LegacyWidgetMapping("customer-sidebar", "customers.detail-drawer"),
            LegacyWidgetMapping("private-domain-task-board", "tasks.private-domain"),
        ),
    ),
)


def validate_ecommerce_workshop_legacy_migration(
    bundles: Iterable[LoadedBundle],
) -> tuple[LegacyMigrationValidation, ...]:
    """Fail closed unless every frozen legacy capability is mapped and retained."""

    loaded_bundles = tuple(bundles)
    legacy_by_id = {
        legacy.legacy_id: legacy
        for bundle in loaded_bundles
        for legacy in bundle.legacy_workshops
    }
    modules_by_id = {
        module.module_id: module
        for bundle in loaded_bundles
        for module in bundle.workshop_modules
    }
    expected_sources = {rule.source_id for rule in ECOMMERCE_LEGACY_MIGRATION_RULES}
    if set(legacy_by_id) != expected_sources:
        raise EcommerceWorkshopMigrationError(
            "legacy source set does not match the frozen ecommerce migration whitelist"
        )

    validations: list[LegacyMigrationValidation] = []
    for rule in ECOMMERCE_LEGACY_MIGRATION_RULES:
        source = legacy_by_id[rule.source_id]
        target = modules_by_id.get(rule.target_module_id)
        if target is None:
            raise EcommerceWorkshopMigrationError(
                f"target module is missing for {rule.source_id}"
            )
        if source.source_path != rule.source_path:
            raise EcommerceWorkshopMigrationError(
                f"legacy source path drifted for {rule.source_id}"
            )

        mapped_widget_ids = {
            mapping.source_widget_id for mapping in rule.mapped_widgets
        }
        missing_widgets = tuple(
            widget_id
            for widget_id in source.widget_ids
            if widget_id not in mapped_widget_ids
        )
        missing_objects = tuple(
            object_id
            for object_id in source.required_objects
            if object_id not in target.required_objects
        )
        source_ref_preserved = source.source_path in target.legacy_asset_refs
        legacy_route_preserved = source.route in target.legacy_redirects
        if (
            missing_widgets
            or missing_objects
            or not source_ref_preserved
            or not legacy_route_preserved
        ):
            raise EcommerceWorkshopMigrationError(
                f"legacy capability conservation failed for {rule.source_id}"
            )

        validations.append(
            LegacyMigrationValidation(
                source_id=rule.source_id,
                target_module_id=rule.target_module_id,
                mapped_widgets=rule.mapped_widgets,
                missing_widget_ids=missing_widgets,
                missing_object_ids=missing_objects,
                source_ref_preserved=source_ref_preserved,
                legacy_route_preserved=legacy_route_preserved,
            )
        )
    return tuple(validations)
