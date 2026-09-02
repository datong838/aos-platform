"""Bounded tenant-safe reader for canonical aftersales original events."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from functools import partial
from typing import Any

import psycopg
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.db import connect_read_only
from aos_api.ecommerce_operation_case_contracts import ExactAuthorityRevisionRef
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ConnectFactory = Callable[[], AbstractContextManager[Any]]


class AftersaleEventOriginal(AipContractModel):
    event_id: str = Field(min_length=1, max_length=300)
    source_revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_type: str = Field(min_length=1, max_length=120)
    status: str = Field(min_length=1, max_length=120)
    occurred_at: datetime
    order_ref: ExactAuthorityRevisionRef
    order_line_ref: ExactAuthorityRevisionRef | None = None

    @field_validator("occurred_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("aftersale event time requires a timezone")
        return value

    @model_validator(mode="after")
    def _source_identity_differs_from_order(self) -> AftersaleEventOriginal:
        if self.event_id == self.order_ref.resource_id:
            raise ValueError("aftersale event and order identities must differ")
        return self


class EcommerceAftersaleEventReaderError(RuntimeError):
    pass


class EcommerceAftersaleEventReader:
    def __init__(self, *, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or partial(
            connect_read_only, inherit_scope=False
        )

    def read(
        self,
        *,
        org_id: str,
        project_id: str,
        cutoff: datetime,
        limit: int = 50,
    ) -> list[AftersaleEventOriginal]:
        if cutoff.utcoffset() is None:
            raise ValueError("aftersale cutoff requires a timezone")
        if not 1 <= limit <= 50:
            raise ValueError("aftersale limit must be between 1 and 50")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        try:
            with self._connect_factory() as conn:
                apply_transaction_scope(conn, scope)
                rows = conn.execute(
                    "SELECT org_id,project_id,event_id,source_revision,source_hash,event_type,status,"
                    "occurred_at,order_resource_id,order_revision,order_content_hash,"
                    "order_line_resource_id,order_line_revision,order_line_content_hash "
                    "FROM ecommerce_aftersale_event WHERE org_id=%s AND project_id=%s "
                    "AND occurred_at<=%s ORDER BY occurred_at DESC,event_id DESC,"
                    "source_revision DESC LIMIT %s",
                    (*scope.key, cutoff, limit),
                ).fetchall()
            return [self._item(row, scope=scope) for row in rows]
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise EcommerceAftersaleEventReaderError(
                "canonical aftersales event read failed closed"
            ) from exc

    @staticmethod
    def _item(
        row: dict[str, Any], *, scope: TenantScope
    ) -> AftersaleEventOriginal:
        if (row["org_id"], row["project_id"]) != scope.key:
            raise ValueError("aftersale event tenant scope drift")
        line_values = (
            row["order_line_resource_id"],
            row["order_line_revision"],
            row["order_line_content_hash"],
        )
        if any(value is None for value in line_values) and not all(
            value is None for value in line_values
        ):
            raise ValueError("partial order line exact ref")
        order_line_ref = None
        if all(value is not None for value in line_values):
            order_line_ref = ExactAuthorityRevisionRef(
                resource_id=row["order_line_resource_id"],
                revision=row["order_line_revision"],
                content_hash=row["order_line_content_hash"],
            )
        return AftersaleEventOriginal(
            event_id=row["event_id"],
            source_revision=row["source_revision"],
            source_hash=row["source_hash"],
            event_type=row["event_type"],
            status=row["status"],
            occurred_at=row["occurred_at"],
            order_ref=ExactAuthorityRevisionRef(
                resource_id=row["order_resource_id"],
                revision=row["order_revision"],
                content_hash=row["order_content_hash"],
            ),
            order_line_ref=order_line_ref,
        )


__all__ = [
    "AftersaleEventOriginal",
    "EcommerceAftersaleEventReader",
    "EcommerceAftersaleEventReaderError",
]
