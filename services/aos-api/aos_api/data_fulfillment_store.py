"""BI-W2-03 exact FulfillmentReceipt binding Store without state inference."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

import psycopg

from aos_api.data_requirement_contracts import DataFulfillmentReceiptRecord
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class DataFulfillmentStoreError(RuntimeError): pass
class DataFulfillmentConflict(DataFulfillmentStoreError): pass
class DataFulfillmentIdempotencyConflict(DataFulfillmentStoreError): pass
class DataFulfillmentValidationError(DataFulfillmentStoreError): pass


@dataclass(frozen=True, slots=True)
class DataFulfillmentBindResult:
    receipt_id: str
    etag: str
    replayed: bool


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def canonical_fulfillment_content_hash(item: DataFulfillmentReceiptRecord) -> str:
    payload = item.model_dump(mode="python", by_alias=True); payload.pop("contentHash", None)
    return f"sha256:{_hash(payload)}"


class DataFulfillmentStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def bind(self, scope: TenantScope, actor: str, idempotency_key: str, item: DataFulfillmentReceiptRecord) -> DataFulfillmentBindResult:
        if scope.key != (item.tenant.org_id, item.tenant.project_id): raise DataFulfillmentValidationError("tenant scope mismatch")
        if actor != item.created_by or not actor: raise DataFulfillmentValidationError("actor must match createdBy")
        if not idempotency_key.strip() or len(idempotency_key) > 200: raise DataFulfillmentValidationError("idempotency key is invalid")
        if item.content_hash != canonical_fulfillment_content_hash(item): raise DataFulfillmentValidationError("content hash mismatch")
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = _hash({"operation": "fulfillment.bind", "receipt": payload})
        params = (
            item.fulfillment_id, item.receipt_id, item.requirement_ref.resource_id,
            item.requirement_ref.revision, item.requirement_ref.content_hash[7:], item.status.value,
            json.dumps(payload["artifactRefs"], separators=(",", ":")),
            json.dumps(payload["sourceReadinessRef"], separators=(",", ":")),
            item.cutoff_at, item.fulfilled_at, item.content_hash[7:], actor,
            idempotency_key, request_hash,
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute("SELECT bound_receipt_id,result_content_hash,replayed FROM data_fulfillment_bind_biw2_003(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)", params).fetchone()
                if row is None: raise DataFulfillmentStoreError("binding returned no result")
                conn.commit()
        except psycopg.Error as exc:
            if exc.sqlstate == "DF002": raise DataFulfillmentIdempotencyConflict("idempotency conflict") from exc
            if exc.sqlstate in {"DF001", "23505"}: raise DataFulfillmentConflict("fulfillment binding conflict") from exc
            raise
        content_hash = f"sha256:{str(row['result_content_hash']).strip()}"
        return DataFulfillmentBindResult(str(row["bound_receipt_id"]), content_hash, bool(row["replayed"]))
