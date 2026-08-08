"""Transactional, tenant, idempotency, tombstone and checkpoint tests."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from aos_api.ecom_consistency_store import (
    EcomConsistencyStore,
    ecom_ingest_receipt,
    metadata,
)
from aos_api.ecom_core_models import (
    BatchCommand,
    CheckpointPosition,
    CoreLinkRecord,
    CoreObjectRecord,
    EcomConsistencyError,
    StorageIdentity,
    SyncScope,
)
from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue, StableCursor
from test_ecom_core_models import VALID_PROPERTIES


NOW = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store() -> EcomConsistencyStore:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return EcomConsistencyStore(engine)


def links_for_default_shop(store: EcomConsistencyStore) -> list[dict]:
    return store.list_links(
        org_id="org-a",
        workspace_id="workspace-a",
        platform="synthetic",
        shop_or_marketplace_id="shop-a",
    )


def ident(
    external_id: str,
    *,
    org: str = "org-a",
    workspace: str = "workspace-a",
    shop: str = "shop-a",
) -> StorageIdentity:
    return ExternalIdentityKey(
        org_id=org,
        workspace_id=workspace,
        platform="synthetic",
        shop_or_marketplace_id=shop,
        external_id=external_id,
    )


def obj(
    object_type: str,
    external_id: str,
    *,
    when: datetime = NOW,
    identity: StorageIdentity | None = None,
    deleted: bool = False,
    properties: dict | None = None,
) -> CoreObjectRecord:
    return CoreObjectRecord(
        identity=identity or ident(external_id),
        object_type=object_type,
        source_updated_at=when,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw(
            "DELETED" if deleted else "ACTIVE",
            {"DELETED": "deleted", "ACTIVE": "active"},
        ),
        is_deleted=deleted,
        properties={} if deleted else (properties or VALID_PROPERTIES[object_type]),
    )


def scope(*, org="org-a", workspace="workspace-a", shop="shop-a", stream="catalog"):
    return SyncScope(
        org_id=org,
        workspace_id=workspace,
        platform="synthetic",
        shop_or_marketplace_id=shop,
        stream=stream,
    )


def batch(
    *objects: CoreObjectRecord,
    key: str = "page-1",
    expected: int = 0,
    at: datetime | None = None,
    cursor_id: str | None = None,
    batch_scope: SyncScope | None = None,
    links: list[CoreLinkRecord] | None = None,
) -> BatchCommand:
    link_items = links or []
    latest = max(
        [record.cursor_key() for record in objects]
        + [link.cursor_key() for link in link_items]
    )
    return BatchCommand(
        scope=batch_scope or scope(),
        idempotency_key=key,
        expected_checkpoint_version=expected,
        next_checkpoint=StableCursor(
            source_updated_at_utc=at or latest[0],
            external_id=cursor_id or latest[1],
        ),
        objects=list(objects),
        links=link_items,
    )


def shop_product_link(when: datetime = NOW, *, deleted: bool = False) -> CoreLinkRecord:
    return CoreLinkRecord(
        link_type="Shop.sellsProduct",
        source_type="Shop",
        source=ident("shop-object"),
        target_type="Product",
        target=ident("product-1"),
        source_updated_at=when,
        cursor_external_id="shop-product-link",
        is_deleted=deleted,
    )


def test_object_link_checkpoint_and_receipt_commit_together(store: EcomConsistencyStore) -> None:
    command = batch(
        obj("Product", "product-1"),
        obj("Shop", "shop-object"),
        links=[shop_product_link()],
    )
    result = store.apply_batch(command)
    assert result.objects_written == 2
    assert result.links_written == 1
    assert result.checkpoint_version == 1
    stored_product = store.get_object(ident("product-1"), "Product")
    assert stored_product is not None
    assert stored_product["properties"]["createdAtSourceTimezone"] == "+0800"
    assert len(links_for_default_shop(store)) == 1


def test_idempotent_replay_returns_saved_result_without_advancing(store: EcomConsistencyStore) -> None:
    command = batch(obj("Product", "product-1"))
    first = store.apply_batch(command)
    replay = store.apply_batch(command)
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.checkpoint_version == 1
    assert store.get_checkpoint(command)["version"] == 1


def test_same_idempotency_key_with_different_hash_conflicts(store: EcomConsistencyStore) -> None:
    first = batch(obj("Product", "product-1"))
    store.apply_batch(first)
    changed_props = {**VALID_PROPERTIES["Product"], "title": "changed"}
    changed = batch(obj("Product", "product-1", properties=changed_props))
    with pytest.raises(EcomConsistencyError) as caught:
        store.apply_batch(changed)
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_request_hash_is_invariant_to_semantic_batch_order() -> None:
    product = obj("Product", "product-1")
    shop = obj("Shop", "shop-object")
    first = batch(product, shop)
    reordered = batch(shop, product)
    assert first.request_hash() == reordered.request_hash()


def test_concurrent_same_idempotency_key_replays_original_result(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'ecom-concurrent.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    metadata.create_all(engine)
    concurrent_stores = (EcomConsistencyStore(engine), EcomConsistencyStore(engine))
    command = batch(obj("Product", "product-1"), key="same-concurrent-page")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda index: concurrent_stores[index].apply_batch(command),
                range(2),
            )
        )
    assert sorted(result.replayed for result in results) == [False, True]
    assert {result.checkpoint_version for result in results} == {1}


def test_same_source_version_with_different_payload_allows_reprojection(store: EcomConsistencyStore) -> None:
    """D5-E2: Same source_updated_at + different payload_hash now allows UPDATE (re-projection).

    Previously this raised SOURCE_VERSION_CONFLICT and rolled back the batch.
    Now it falls through to UPDATE to support derived metric recompute (e.g., CustomerLite order_count).
    """
    existing = obj("Product", "z-existing")
    first = batch(existing, key="first", cursor_id="z-existing")
    store.apply_batch(first)
    changed = obj(
        "Product",
        "z-existing",
        properties={**VALID_PROPERTIES["Product"], "title": "conflict"},
    )
    new_before_conflict = obj("Product", "a-new")
    second = batch(
        new_before_conflict,
        changed,
        key="second",
        expected=1,
        cursor_id="z-existing",
    )
    # D5-E2: No longer raises — both objects are written (re-projection)
    result = store.apply_batch(second)
    assert result.objects_written >= 1
    # The new object should exist
    assert store.get_object(ident("a-new"), "Product") is not None
    # The changed object should have the updated title
    updated = store.get_object(ident("z-existing"), "Product")
    assert updated is not None
    assert updated["properties"].get("title") == "conflict"


def test_older_source_version_is_ignored(store: EcomConsistencyStore) -> None:
    store.apply_batch(batch(obj("Product", "p-1"), key="new"))
    stale = obj("Product", "p-1", when=NOW - timedelta(minutes=1))
    result = store.apply_batch(
        batch(stale, key="old", expected=1, at=NOW, cursor_id="p-1")
    )
    assert result.objects_ignored == 1
    stored_time = store.get_object(ident("p-1"), "Product")["source_updated_at"]
    # SQLite drops timezone metadata; PostgreSQL preserves TIMESTAMPTZ.
    assert stored_time.replace(tzinfo=stored_time.tzinfo or timezone.utc) == NOW


@pytest.mark.parametrize(
    ("org", "workspace", "shop"),
    [
        ("org-b", "workspace-a", "shop-a"),
        ("org-a", "workspace-b", "shop-a"),
        ("org-a", "workspace-a", "shop-b"),
    ],
)
def test_same_external_id_is_isolated_by_org_workspace_and_shop(
    store: EcomConsistencyStore, org: str, workspace: str, shop: str
) -> None:
    store.apply_batch(batch(obj("Order", "same-id"), batch_scope=scope(stream="orders")))
    other_identity = ident("same-id", org=org, workspace=workspace, shop=shop)
    other_scope = scope(org=org, workspace=workspace, shop=shop, stream="orders")
    store.apply_batch(
        batch(
            obj("Order", "same-id", identity=other_identity),
            key="other",
            batch_scope=other_scope,
        )
    )
    assert store.get_object(ident("same-id"), "Order") is not None
    assert store.get_object(other_identity, "Order") is not None


def test_link_listing_requires_full_shop_scope(store: EcomConsistencyStore) -> None:
    store.apply_batch(
        batch(
            obj("Product", "product-1"),
            obj("Shop", "shop-object"),
            links=[shop_product_link()],
        )
    )
    other_shop = "shop-b"
    other_scope = scope(shop=other_shop)
    other_product = obj(
        "Product",
        "product-1",
        identity=ident("product-1", shop=other_shop),
    )
    other_shop_object = obj(
        "Shop",
        "shop-object",
        identity=ident("shop-object", shop=other_shop),
    )
    other_link = CoreLinkRecord(
        link_type="Shop.sellsProduct",
        source_type="Shop",
        source=ident("shop-object", shop=other_shop),
        target_type="Product",
        target=ident("product-1", shop=other_shop),
        source_updated_at=NOW,
        cursor_external_id="shop-product-link",
    )
    store.apply_batch(
        batch(
            other_product,
            other_shop_object,
            key="other-shop",
            batch_scope=other_scope,
            links=[other_link],
        )
    )
    assert len(links_for_default_shop(store)) == 1
    assert len(
        store.list_links(
            org_id="org-a",
            workspace_id="workspace-a",
            platform="synthetic",
            shop_or_marketplace_id=other_shop,
        )
    ) == 1


def test_dangling_link_is_ignored_and_objects_are_preserved(store: EcomConsistencyStore) -> None:
    """D5-E1: Dangling links are now counted as links_ignored instead of rolling back the batch.

    Objects are still written (objects-first + links-with-precheck pattern).
    The dangling link can be retrieved via get_last_dangling_links() for DLQ processing.
    """
    dangling = CoreLinkRecord(
        link_type="Shop.sellsProduct",
        source_type="Shop",
        source=ident("shop-object"),
        target_type="Product",
        target=ident("missing-product"),
        source_updated_at=NOW,
        cursor_external_id="dangling-link",
    )
    command = batch(obj("Shop", "shop-object"), key="dangling", links=[dangling])
    # D5-E1: No longer raises — dangling link is ignored, objects are preserved
    result = store.apply_batch(command)
    # Object should exist (not rolled back)
    assert store.get_object(ident("shop-object"), "Shop") is not None
    # Link should be ignored
    assert result.links_ignored >= 1
    # Dangling links available for DLQ
    dangling_links = store.get_last_dangling_links()
    assert len(dangling_links) >= 1


def test_object_tombstone_also_tombstones_attached_links(store: EcomConsistencyStore) -> None:
    store.apply_batch(
        batch(
            obj("Product", "product-1"),
            obj("Shop", "shop-object"),
            links=[shop_product_link()],
        )
    )
    later = NOW + timedelta(minutes=1)
    deleted = obj("Product", "product-1", when=later, deleted=True)
    result = store.apply_batch(
        batch(deleted, key="delete", expected=1, at=later, cursor_id="product-1")
    )
    assert result.objects_tombstoned == 1
    assert store.get_object(ident("product-1"), "Product")["deleted_at"] is not None
    assert links_for_default_shop(store)[0]["deleted_at"] is not None


def test_explicit_link_tombstone_is_idempotent(store: EcomConsistencyStore) -> None:
    store.apply_batch(
        batch(
            obj("Product", "product-1"),
            obj("Shop", "shop-object"),
            links=[shop_product_link()],
        )
    )
    later = NOW + timedelta(minutes=1)
    command = batch(
        key="delete-link",
        expected=1,
        at=later,
        links=[shop_product_link(later, deleted=True)],
    )
    first = store.apply_batch(command)
    replay = store.apply_batch(command)
    assert first.links_tombstoned == 1
    assert replay.replayed is True


def test_checkpoint_cas_conflict_rolls_back_new_object(store: EcomConsistencyStore) -> None:
    first = batch(obj("Product", "p-1"), key="first")
    store.apply_batch(first)
    stale_writer = batch(
        obj("Product", "p-2", when=NOW + timedelta(seconds=1)),
        key="stale",
        expected=0,
        at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(EcomConsistencyError) as caught:
        store.apply_batch(stale_writer)
    assert caught.value.code == "CHECKPOINT_CAS_CONFLICT"
    assert store.get_object(ident("p-2"), "Product") is None


def test_checkpoint_cannot_skip_past_last_stable_batch_cursor(
    store: EcomConsistencyStore,
) -> None:
    command = batch(obj("Product", "p-1"), at=NOW, cursor_id="z")
    with pytest.raises(EcomConsistencyError) as caught:
        store.apply_batch(command)
    assert caught.value.code == "CHECKPOINT_BOUNDARY_INVALID"
    assert store.get_object(ident("p-1"), "Product") is None


def test_cascade_tombstone_blocks_late_link_after_object_resurrection(
    store: EcomConsistencyStore,
) -> None:
    store.apply_batch(
        batch(
            obj("Product", "product-1"),
            obj("Shop", "shop-object"),
            links=[shop_product_link()],
        )
    )
    deleted_at = NOW + timedelta(minutes=10)
    store.apply_batch(
        batch(
            obj("Product", "product-1", when=deleted_at, deleted=True),
            key="delete-object",
            expected=1,
        )
    )
    resurrected_at = NOW + timedelta(minutes=20)
    store.apply_batch(
        batch(
            obj("Product", "product-1", when=resurrected_at),
            key="resurrect-object",
            expected=2,
        )
    )
    late_link = shop_product_link(NOW + timedelta(minutes=5))
    result = store.apply_batch(
        batch(
            key="late-link",
            expected=3,
            at=resurrected_at,
            cursor_id="product-1",
            links=[late_link],
        )
    )
    assert result.links_ignored == 1
    assert links_for_default_shop(store)[0]["deleted_at"] is not None


def test_object_tombstone_advances_an_older_explicit_link_tombstone(
    store: EcomConsistencyStore,
) -> None:
    store.apply_batch(
        batch(
            obj("Product", "product-1"),
            obj("Shop", "shop-object"),
            links=[shop_product_link()],
        )
    )
    link_deleted_at = NOW + timedelta(minutes=5)
    store.apply_batch(
        batch(
            key="delete-link-first",
            expected=1,
            links=[shop_product_link(link_deleted_at, deleted=True)],
        )
    )
    object_deleted_at = NOW + timedelta(minutes=10)
    store.apply_batch(
        batch(
            obj("Product", "product-1", when=object_deleted_at, deleted=True),
            key="delete-object-later",
            expected=2,
        )
    )
    stored_link = links_for_default_shop(store)[0]
    assert stored_link["deleted_at"].replace(
        tzinfo=stored_link["deleted_at"].tzinfo or timezone.utc
    ) == object_deleted_at

    resurrected_at = NOW + timedelta(minutes=20)
    store.apply_batch(
        batch(
            obj("Product", "product-1", when=resurrected_at),
            key="resurrect-after-explicit-link-delete",
            expected=3,
        )
    )
    late_link = shop_product_link(NOW + timedelta(minutes=7))
    result = store.apply_batch(
        batch(
            key="late-link-after-explicit-delete",
            expected=4,
            at=resurrected_at,
            cursor_id="product-1",
            links=[late_link],
        )
    )
    assert result.links_ignored == 1


def test_checkpoint_regression_is_rejected_without_writes(store: EcomConsistencyStore) -> None:
    first = batch(obj("Product", "p-1"), key="first")
    store.apply_batch(first)
    regression = batch(
        obj("Product", "p-old", when=NOW - timedelta(seconds=1)),
        key="regress",
        expected=1,
        at=NOW - timedelta(seconds=1),
        cursor_id="p-old",
    )
    with pytest.raises(EcomConsistencyError) as caught:
        store.apply_batch(regression)
    assert caught.value.code == "CHECKPOINT_REGRESSION"
    assert store.get_checkpoint(first)["version"] == 1


def test_batch_model_rejects_cross_tenant_link_before_transaction() -> None:
    with pytest.raises(ValidationError, match="cross-tenant"):
        CoreLinkRecord(
            link_type="Order.lines",
            source_type="Order",
            source=ident("o-1"),
            target_type="OrderLine",
            target=ident("line-1", org="org-b"),
            source_updated_at=NOW,
            cursor_external_id="cross-tenant-link",
        )


def test_apply_revalidates_mutated_nested_batch_before_transaction(
    store: EcomConsistencyStore,
) -> None:
    command = batch(obj("Product", "product-1"))
    command.objects.append(
        obj("Product", "outside", identity=ident("outside", org="org-b"))
    )
    with pytest.raises(ValidationError, match="outside the batch scope"):
        store.apply_batch(command)
    assert store.get_object(ident("product-1"), "Product") is None
