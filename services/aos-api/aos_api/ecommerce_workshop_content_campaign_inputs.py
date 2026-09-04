"""Tenant-safe same-cutoff reader for real content-campaign business inputs."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Any

import psycopg

from aos_api.db import connect_read_only
from aos_api.ecommerce_content_campaign_authority_store import (
    ContentCampaignAuthorityReadError,
    EcommerceContentCampaignAuthorityStore,
)
from aos_api.ecommerce_workshop_content_campaign_inputs_contracts import (
    ContentCampaignInputLedger,
    ContentCampaignInputRef,
    ContentCampaignInventoryInput,
    ContentCampaignPlanInput,
    ContentCampaignProductInput,
    WorkshopContentCampaignInputsEnvelope,
)
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ConnectFactory = Callable[[], AbstractContextManager[Any]]
Clock = Callable[[], datetime]


def _non_negative_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        return None
    return int(number)


class EcommerceWorkshopContentCampaignInputs:
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        connect_factory: ConnectFactory | None = None,
        campaign_store: EcommerceContentCampaignAuthorityStore | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._connect_factory = connect_factory or partial(
            connect_read_only, inherit_scope=False
        )
        self._campaign_store = campaign_store or EcommerceContentCampaignAuthorityStore()

    def read(self, *, org_id: str, project_id: str):
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("content-campaign input clock requires timezone")
        scope = TenantScope(org_id, project_id)
        products: list[ContentCampaignProductInput] = []
        inventory: list[ContentCampaignInventoryInput] = []
        plans: list[ContentCampaignPlanInput] = []
        unavailable: list[str] = []
        try:
            with self._connect_factory() as conn:
                apply_transaction_scope(conn, scope)
                rows = conn.execute(
                    "SELECT object_type,external_id,properties,source_updated_at,payload_hash "
                    "FROM ecom_object WHERE org_id=%s AND workspace_id=%s "
                    "AND object_type IN (%s,%s) AND deleted_at IS NULL "
                    "AND source_updated_at<=%s ORDER BY object_type,source_updated_at DESC,external_id DESC LIMIT 200",
                    (*scope.key, "Product", "ProductSku", cutoff),
                ).fetchall()
            product_rows = [row for row in rows if row["object_type"] == "Product"][:100]
            sku_rows = [row for row in rows if row["object_type"] == "ProductSku"][:100]
            products = [self._product(row) for row in product_rows]
            product_by_source_id = {
                item.product_ref.resource_id.rsplit(":", 1)[-1]: item.product_ref
                for item in products
            }
            inventory = [self._inventory(row, product_by_source_id) for row in sku_rows]
        except (psycopg.Error, KeyError, TypeError, ValueError):
            unavailable.extend(["products", "inventory"])
        try:
            snapshot = self._campaign_store.read_snapshot(scope, cutoff=cutoff, limit=100)
            if snapshot.errors:
                raise ContentCampaignAuthorityReadError("campaign snapshot partial")
            plans = [self._campaign(item) for item in snapshot.campaigns]
            plans.extend(self._calendar(item) for item in snapshot.calendar_entries)
        except ContentCampaignAuthorityReadError:
            unavailable.append("plans")
        status = "blocked" if len(unavailable) == 3 else ("partial" if unavailable else "ready")
        unmatched = sum(item.product_ref is None for item in inventory)
        return WorkshopContentCampaignInputsEnvelope(
            tenant={"orgId": org_id, "projectId": project_id},
            evaluated_at=cutoff,
            data_cutoff=cutoff,
            status=status,
            products=products,
            inventory=inventory,
            plans=plans,
            ledger=ContentCampaignInputLedger(
                products=len(products), inventory=len(inventory), plans=len(plans),
                unmatched_inventory=unmatched,
            ),
            unavailable_groups=unavailable,
        )

    @staticmethod
    def _ref(resource_type: str, row: dict[str, Any]) -> ContentCampaignInputRef:
        return ContentCampaignInputRef(
            resource_type=resource_type,
            resource_id=str(row["external_id"]),
            content_hash="sha256:" + str(row["payload_hash"]),
            authority="ecom_object",
        )

    @classmethod
    def _product(cls, row: dict[str, Any]) -> ContentCampaignProductInput:
        props = dict(row["properties"])
        title = str(props.get("title") or "").strip() or "商品名称来源未提供"
        return ContentCampaignProductInput(
            product_ref=cls._ref("Product", row),
            title=title,
            price=str(props["price"]) if props.get("price") is not None else None,
            available_stock=_non_negative_int(props.get("stock")),
            business_status=str(props["state"]) if props.get("state") is not None else None,
            source_updated_at=row["source_updated_at"],
        )

    @classmethod
    def _inventory(cls, row, products):
        props = dict(row["properties"])
        return ContentCampaignInventoryInput(
            sku_ref=cls._ref("ProductSku", row),
            product_ref=products.get(str(props.get("productId", ""))),
            stock=_non_negative_int(props.get("stock")),
            stock_alarm=_non_negative_int(props.get("stockAlarm")),
            stock_health=props.get("stock_health"),
            source_updated_at=row["source_updated_at"],
        )

    @staticmethod
    def _authority_ref(resource_type, observation, identity):
        return ContentCampaignInputRef(
            resource_type=resource_type,
            resource_id=identity,
            revision=observation.revision.revision,
            content_hash="sha256:" + observation.revision.content_hash,
            authority="content_campaign_authority",
        )

    @classmethod
    def _campaign(cls, observation):
        item = observation.revision
        return ContentCampaignPlanInput(
            plan_ref=cls._authority_ref("CampaignRevision", observation, item.campaign_id),
            lifecycle=item.lifecycle.value,
            channel_ids=item.channel_ids,
            source_updated_at=item.created_at,
        )

    @classmethod
    def _calendar(cls, observation):
        item = observation.revision
        return ContentCampaignPlanInput(
            plan_ref=cls._authority_ref("CalendarEntryRevision", observation, item.entry_id),
            lifecycle=item.lifecycle.value,
            channel_ids=[],
            local_start=item.local_start,
            local_end=item.local_end,
            source_updated_at=item.created_at,
        )


__all__ = ["EcommerceWorkshopContentCampaignInputs"]
