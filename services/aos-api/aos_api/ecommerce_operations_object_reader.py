"""Bounded tenant-safe exact-ref reader for Operations transaction objects."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from functools import partial
from typing import Any, Literal

import psycopg
from pydantic import Field, field_validator

from aos_api.aip_contracts import AipContractModel
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


class EcommerceOperationsObjectReader:
    def __init__(self, *, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or partial(
            connect_read_only, inherit_scope=False
        )

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
