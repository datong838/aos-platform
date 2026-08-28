"""Tenant-safe bounded reader for canonical ProductSku inventory originals."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.ecommerce_inventory_reader_contracts import (
    InventoryHealth,
    InventoryObjectRevision,
    InventoryReadEnvelope,
    InventoryReadItem,
    InventoryReadPage,
)
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ConnectFactory = Callable[[], AbstractContextManager[Any]]


class EcommerceInventoryReaderError(RuntimeError):
    pass


def _optional_non_negative_integer(value: object, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    text = str(value).strip()
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError(f"{field} must be a non-negative integer")
    return int(number)


class EcommerceInventoryReader:
    def __init__(self, *, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or partial(
            connect,
            inherit_scope=False,
        )

    def read(
        self,
        *,
        org_id: str,
        project_id: str,
        cutoff: datetime,
        limit: int,
    ) -> InventoryReadEnvelope:
        scope = TenantScope(org_id=org_id, project_id=project_id)
        if cutoff.utcoffset() is None:
            raise ValueError("Inventory cutoff requires a timezone")
        if not 1 <= limit <= 100:
            raise ValueError("Inventory limit must be between 1 and 100")

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                rows = conn.execute(
                    """SELECT external_id,properties,source_updated_at,payload_hash
                         FROM ecom_object
                        WHERE org_id=%s AND workspace_id=%s AND object_type=%s
                          AND deleted_at IS NULL AND source_updated_at<=%s
                        ORDER BY source_updated_at DESC, external_id DESC
                        LIMIT %s""",
                    (*scope.key, "ProductSku", cutoff, limit + 1),
                ).fetchall()
                items = [self._item(row) for row in rows[:limit]]
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise EcommerceInventoryReaderError(
                "canonical ProductSku inventory read failed closed"
            ) from exc

        return InventoryReadEnvelope(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            cutoff=cutoff,
            items=items,
            page=InventoryReadPage(
                limit=limit,
                count=len(items),
                unknown_count=sum(
                    item.stock is None
                    or item.stock_alarm is None
                    or item.stock_health is None
                    for item in items
                ),
                has_more=len(rows) > limit,
            ),
        )

    @staticmethod
    def _item(row: dict[str, Any]) -> InventoryReadItem:
        properties = dict(row["properties"])
        object_id = str(row["external_id"])
        payload_hash = str(row["payload_hash"]).strip()
        return InventoryReadItem(
            object_id=object_id,
            stock=_optional_non_negative_integer(properties.get("stock"), field="stock"),
            stock_alarm=_optional_non_negative_integer(
                properties.get("stockAlarm"),
                field="stockAlarm",
            ),
            stock_health=(
                InventoryHealth(properties["stock_health"])
                if properties.get("stock_health") is not None
                else None
            ),
            source_updated_at=row["source_updated_at"],
            revision=InventoryObjectRevision(
                resource_id=object_id,
                content_hash="sha256:" + payload_hash,
            ),
        )


__all__ = ["EcommerceInventoryReader", "EcommerceInventoryReaderError"]
