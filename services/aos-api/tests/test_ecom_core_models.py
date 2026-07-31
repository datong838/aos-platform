"""Core-7 model and stable incremental window tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.ecom_core_models import (
    BatchCommand,
    CheckpointPosition,
    CoreLinkRecord,
    CoreObjectRecord,
    StorageIdentity,
    SyncScope,
    stable_incremental_window,
)
from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue, StableCursor


NOW = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)


VALID_PROPERTIES = {
    "Shop": {"name": "Synthetic shop", "status": "active", "currency": "CNY", "timezone": "Asia/Shanghai"},
    "Product": {"shopId": "s-1", "title": "Synthetic product", "status": "active", "categoryId": "c-1", "createdAt": "2026-07-31T18:00:00+08:00", "updatedAt": "2026-07-31T18:00:00+08:00"},
    "ProductSku": {"productId": "p-1", "status": "active", "barcode": "000000", "price": "12.30", "currency": "CNY", "updatedAt": "2026-07-31T18:00:00+08:00"},
    "Category": {"parentCategoryId": "root", "name": "Synthetic category", "status": "active", "updatedAt": "2026-07-31T18:00:00+08:00"},
    "Order": {"shopId": "s-1", "status": "paid", "totalAmount": "12.30", "currency": "CNY", "createdAt": "2026-07-31T18:00:00+08:00", "updatedAt": "2026-07-31T18:00:00+08:00"},
    "OrderLine": {"orderId": "o-1", "skuId": "sku-1", "quantity": 1, "unitPrice": "12.30", "lineAmount": "12.30", "currency": "CNY", "updatedAt": "2026-07-31T18:00:00+08:00"},
    "Shipment": {"orderId": "o-1", "status": "shipped", "carrier": "synthetic", "trackingNo": "track-1", "shippedAt": "2026-07-31T18:00:00+08:00", "updatedAt": "2026-07-31T18:00:00+08:00"},
}


def identity(
    external_id: str,
    *,
    org_id: str = "org-a",
    workspace_id: str = "workspace-a",
    platform: str = "synthetic",
    shop_id: str = "shop-a",
) -> StorageIdentity:
    return ExternalIdentityKey(
        org_id=org_id,
        workspace_id=workspace_id,
        platform=platform,
        shop_or_marketplace_id=shop_id,
        external_id=external_id,
    )


def record(object_type: str, external_id: str, **changes) -> CoreObjectRecord:
    values = {
        "identity": identity(external_id),
        "object_type": object_type,
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "status": ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active"}),
        "properties": VALID_PROPERTIES[object_type],
    }
    values.update(changes)
    return CoreObjectRecord(**values)


@pytest.mark.parametrize("object_type", list(VALID_PROPERTIES))
def test_core_seven_accept_required_fields_and_extra_properties(object_type: str) -> None:
    props = {**VALID_PROPERTIES[object_type], "platformExtension": {"safe": True}}
    item = record(object_type, f"id-{object_type}", properties=props)
    assert item.properties["platformExtension"] == {"safe": True}
    assert len(item.payload_hash()) == 64


def test_missing_required_field_is_rejected() -> None:
    props = dict(VALID_PROPERTIES["Order"])
    props.pop("currency")
    with pytest.raises(ValidationError, match="missing required properties"):
        record("Order", "o-1", properties=props)


def test_tombstone_does_not_require_full_business_payload() -> None:
    item = record("Order", "o-1", is_deleted=True, properties={})
    assert item.is_deleted is True


def test_unknown_enum_requires_raw_status() -> None:
    with pytest.raises(ValidationError, match="requires raw_status"):
        record("Product", "p-1", status=ForwardEnumValue.from_raw("", {}))
    item = record("Product", "p-1", status=ForwardEnumValue.from_raw("NEW_VALUE", {}))
    assert item.status.raw_status == "NEW_VALUE"


def test_float_money_is_rejected_at_w1_boundary() -> None:
    props = {**VALID_PROPERTIES["ProductSku"], "price": 12.3}
    with pytest.raises(ValidationError, match="binary float money input is forbidden"):
        record("ProductSku", "sku-1", properties=props)


def test_money_is_normalized_and_half_even_quantized_before_hashing() -> None:
    props = {
        **VALID_PROPERTIES["ProductSku"],
        "price": "12.345",
        "currency": "cny",
    }
    item = record("ProductSku", "sku-1", properties=props)
    assert item.properties["price"] == "12.34"
    assert item.properties["currency"] == "CNY"
    assert item.properties["currencyScale"] == 2


def test_unknown_currency_requires_scale_and_business_time_preserves_source_zone() -> None:
    without_scale = {
        **VALID_PROPERTIES["ProductSku"],
        "price": "1.2345",
        "currency": "XYZ",
    }
    with pytest.raises(ValidationError, match="explicit scale"):
        record("ProductSku", "sku-1", properties=without_scale)
    item = record(
        "ProductSku",
        "sku-1",
        properties={**without_scale, "currencyScale": 3},
    )
    assert item.properties["price"] == "1.234"
    assert item.properties["updatedAt"] == "2026-07-31T10:00:00.000000Z"
    assert item.properties["updatedAtSourceTimezone"] == "+0800"


def test_naive_business_time_is_rejected() -> None:
    props = {
        **VALID_PROPERTIES["Order"],
        "updatedAt": "2026-07-31T10:00:00",
    }
    with pytest.raises(ValidationError, match="time must include timezone"):
        record("Order", "o-1", properties=props)


def test_naive_source_time_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        record("Order", "o-1", source_updated_at=datetime(2026, 7, 31, 10, 0))


def test_public_identity_normalizes_platform_and_preserves_id_case() -> None:
    assert identity("CaseSensitive", platform="Synthetic").platform == "synthetic"
    item = identity("CaseSensitive")
    assert item.external_id == "CaseSensitive"


def test_link_type_and_tenant_are_fail_closed() -> None:
    with pytest.raises(ValidationError, match="requires Order -> OrderLine"):
        CoreLinkRecord(
            link_type="Order.lines",
            source_type="Product",
            source=identity("p-1"),
            target_type="OrderLine",
            target=identity("line-1"),
            source_updated_at=NOW,
            cursor_external_id="bad-shape-link",
        )
    with pytest.raises(ValidationError, match="cross-tenant"):
        CoreLinkRecord(
            link_type="Order.lines",
            source_type="Order",
            source=identity("o-1"),
            target_type="OrderLine",
            target=identity("line-1", org_id="org-b"),
            source_updated_at=NOW,
            cursor_external_id="cross-tenant-link",
        )


def test_batch_rejects_cross_shop_records() -> None:
    scope = SyncScope(
        org_id="org-a",
        workspace_id="workspace-a",
        platform="synthetic",
        shop_or_marketplace_id="shop-a",
        stream="orders",
    )
    outside = record("Order", "o-1", identity=identity("o-1", shop_id="shop-b"))
    with pytest.raises(ValidationError, match="outside the batch scope"):
        BatchCommand(
            scope=scope,
            idempotency_key="page-1",
            expected_checkpoint_version=0,
            next_checkpoint=StableCursor(source_updated_at_utc=NOW, external_id="o-1"),
            objects=[outside],
        )


def test_batch_checkpoint_must_cover_link_source_version() -> None:
    scope = SyncScope(
        org_id="org-a",
        workspace_id="workspace-a",
        platform="synthetic",
        shop_or_marketplace_id="shop-a",
        stream="catalog-links",
    )
    link = CoreLinkRecord(
        link_type="Shop.sellsProduct",
        source_type="Shop",
        source=identity("shop-object"),
        target_type="Product",
        target=identity("product-1"),
        source_updated_at=NOW,
        cursor_external_id="shop-product-link",
    )
    with pytest.raises(ValidationError, match="behind the batch data"):
        BatchCommand(
            scope=scope,
            idempotency_key="page-1",
            expected_checkpoint_version=0,
            next_checkpoint=StableCursor(
                source_updated_at_utc=NOW - timedelta(microseconds=1),
                external_id="z",
            ),
            links=[link],
        )


def test_same_millisecond_cursor_is_stable_and_has_no_gaps() -> None:
    items = [record("Order", ext) for ext in ["o-3", "o-1", "o-2"]]
    window = stable_incremental_window(items, checkpoint=None, lookback_seconds=0)
    assert [item.identity.external_id for item in window] == ["o-1", "o-2", "o-3"]


def test_lookback_includes_late_rows_and_keeps_deterministic_order() -> None:
    checkpoint = StableCursor(source_updated_at_utc=NOW, external_id="o-9")
    late = record("Order", "o-late", source_updated_at=NOW - timedelta(seconds=20))
    too_old = record("Order", "o-old", source_updated_at=NOW - timedelta(seconds=31))
    current = record("Order", "o-new", source_updated_at=NOW + timedelta(seconds=1))
    window = stable_incremental_window(
        [current, too_old, late], checkpoint=checkpoint, lookback_seconds=30
    )
    assert [item.identity.external_id for item in window] == ["o-late", "o-new"]
