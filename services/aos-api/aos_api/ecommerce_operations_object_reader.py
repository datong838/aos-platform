"""Bounded tenant-safe exact-ref reader for Operations transaction objects."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from functools import partial
from typing import Any, Literal

import psycopg
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.db import connect_read_only
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ObjectType = Literal["Order", "OrderLine", "Shipment", "Payment"]
ConnectFactory = Callable[[], AbstractContextManager[Any]]
_OBJECT_TYPES = frozenset({"Order", "OrderLine", "Shipment", "Payment"})


class OperationsObjectRef(AipContractModel):
    object_type: ObjectType
    object_id: str = Field(min_length=1, max_length=300)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_updated_at: datetime

    @field_validator("source_updated_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("operations object time requires a timezone")
        return value


class OperationsObjectReadError(RuntimeError):
    pass


class OperationsObjectPage(AipContractModel):
    items: list[OperationsObjectRef] = Field(max_length=50)
    total_count: int = Field(ge=0)


class OperationsObjectSearchResponse(AipContractModel):
    tenant: TenantContext
    object_type: ObjectType
    query: str = Field(max_length=120)
    data_cutoff: datetime
    offset: int = Field(ge=0, le=100000)
    limit: int = Field(ge=1, le=50)
    total_count: int = Field(ge=0)
    items: list[OperationsObjectRef] = Field(max_length=50)
    next_offset: int | None = Field(default=None, ge=0, le=100000)

    @model_validator(mode="after")
    def _consistent(self):
        if self.data_cutoff.utcoffset() is None:
            raise ValueError("search cutoff requires timezone")
        if len(self.items) > self.limit or len(self.items) > max(0, self.total_count - self.offset):
            raise ValueError("search page count drift")
        if any(item.object_type != self.object_type or item.source_updated_at > self.data_cutoff for item in self.items):
            raise ValueError("search page reference drift")
        following = self.offset + self.limit
        expected = following if following < self.total_count and following <= 100000 else None
        if self.next_offset != expected:
            raise ValueError("search next offset drift")
        return self


class EcommerceOperationsObjectReader:
    def __init__(self, *, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or partial(
            connect_read_only, inherit_scope=False
        )

    def read_page(self, *, org_id: str, project_id: str, object_type: ObjectType,
                  cutoff: datetime, limit: int = 50, query: str = "", offset: int = 0) -> OperationsObjectPage:
        if cutoff.utcoffset() is None:
            raise ValueError("operations object cutoff requires a timezone")
        if object_type not in _OBJECT_TYPES:
            raise ValueError("unsupported operations object type")
        if not 1 <= limit <= 50:
            raise ValueError("operations object limit must be between 1 and 50")
        if type(limit) is not int or type(offset) is not int or not 0 <= offset <= 100000:
            raise ValueError("invalid operations page bounds")
        if not isinstance(query, str) or len(query.strip()) > 120 or "\x00" in query:
            raise ValueError("invalid operations object query")
        query = query.strip()
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        scope = TenantScope(org_id=org_id, project_id=project_id)
        try:
            with self._connect_factory() as conn:
                apply_transaction_scope(conn, scope)
                rows = conn.execute(
                    """WITH filtered AS MATERIALIZED (
                        SELECT object_type,external_id,source_updated_at,payload_hash,platform,shop_or_marketplace_id
                        FROM ecom_object WHERE org_id=%s AND workspace_id=%s
                          AND object_type=%s AND deleted_at IS NULL AND source_updated_at<=%s
                          AND external_id ILIKE %s
                    )
                    SELECT population.total_count,page.*
                    FROM (SELECT COUNT(*) AS total_count FROM filtered) population
                    LEFT JOIN LATERAL (
                        SELECT * FROM filtered ORDER BY source_updated_at DESC,external_id DESC,platform,shop_or_marketplace_id LIMIT %s OFFSET %s
                    ) page ON true""",
                    (*scope.key, object_type, cutoff, pattern, limit, offset),
                ).fetchall()
            if not rows or type(rows[0]["total_count"]) is not int:
                raise ValueError("operations population unavailable")
            total = rows[0]["total_count"]
            items = []
            for row in rows:
                if row["total_count"] != total:
                    raise ValueError("operations population drifted")
                if row["object_type"] is None and offset >= total:
                    continue
                if row["object_type"] != object_type:
                    raise ValueError("operations object type drift")
                items.append(OperationsObjectRef(object_type=object_type,
                    object_id=row["external_id"], content_hash="sha256:" + row["payload_hash"],
                    source_updated_at=row["source_updated_at"]))
            if total < len(items) or len(items) > limit:
                raise ValueError("operations population/window drifted")
            return OperationsObjectPage(items=items, total_count=total)
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise OperationsObjectReadError("canonical Operations population read failed closed") from exc

    def read(
        self,
        *,
        org_id: str,
        project_id: str,
        object_type: ObjectType,
        cutoff: datetime,
        limit: int = 50,
    ) -> list[OperationsObjectRef]:
        if cutoff.utcoffset() is None:
            raise ValueError("operations object cutoff requires a timezone")
        if object_type not in _OBJECT_TYPES:
            raise ValueError("unsupported operations object type")
        if not 1 <= limit <= 50:
            raise ValueError("operations object limit must be between 1 and 50")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        try:
            with self._connect_factory() as conn:
                apply_transaction_scope(conn, scope)
                rows = conn.execute(
                    "SELECT object_type,external_id,source_updated_at,payload_hash "
                    "FROM ecom_object WHERE org_id=%s AND workspace_id=%s "
                    "AND object_type=%s AND deleted_at IS NULL AND source_updated_at<=%s "
                    "ORDER BY source_updated_at DESC,external_id DESC LIMIT %s",
                    (*scope.key, object_type, cutoff, limit),
                ).fetchall()
            items = []
            for row in rows:
                if row["object_type"] != object_type:
                    raise ValueError("operations object type drift")
                items.append(
                    OperationsObjectRef(
                        object_type=row["object_type"],
                        object_id=row["external_id"],
                        content_hash="sha256:" + row["payload_hash"],
                        source_updated_at=row["source_updated_at"],
                    )
                )
            return items
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise OperationsObjectReadError(
                "canonical Operations object read failed closed"
            ) from exc


__all__ = ["EcommerceOperationsObjectReader", "OperationsObjectReadError", "OperationsObjectRef"]
