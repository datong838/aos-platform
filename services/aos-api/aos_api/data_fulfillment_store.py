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
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
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

    def read_exact(
        self, scope: TenantScope, ref: InvestigationExactRef
    ) -> DataFulfillmentReceiptRecord | None:
        """Read original complete authority without inventing legacy fields or timezone."""
        if (ref.resource_type != "DataFulfillmentReceipt" or ref.revision != 1
                or not ref.receipt_id or ref.resource_id != ref.receipt_id):
            raise DataFulfillmentValidationError("an exact fulfillment receipt reference is required")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT f.org_id,f.project_id,f.fulfillment_id,f.receipt_id,
                          f.requirement_id,f.requirement_revision,r.content_hash AS requirement_hash,
                          f.status,f.artifact_refs,f.source_readiness_ref,f.cutoff_at,
                          f.fulfilled_at,f.content_hash,f.created_by,f.authority_data
                     FROM data_fulfillment_receipt f
                     JOIN data_requirement_revision r ON r.org_id=f.org_id
                      AND r.project_id=f.project_id AND r.requirement_id=f.requirement_id
                      AND r.revision=f.requirement_revision
                    WHERE f.org_id=%s AND f.project_id=%s
                      AND f.receipt_id=%s""",
                (*scope.key, ref.receipt_id),
            ).fetchone()
        if row is None:
            return None
        if (
            (row["org_id"], row["project_id"]) != scope.key
            or row["receipt_id"] != ref.receipt_id
            or "sha256:" + str(row["content_hash"]).strip() != ref.content_hash
            or not isinstance(row.get("authority_data"), dict)
        ):
            raise DataFulfillmentValidationError("fulfillment readback identity or status drifted")
        try:
            item = DataFulfillmentReceiptRecord.model_validate(row["authority_data"])
        except (TypeError, ValueError) as exc:
            raise DataFulfillmentValidationError("fulfillment readback payload is invalid") from exc
        if (canonical_fulfillment_content_hash(item) != ref.content_hash
                or item.content_hash != ref.content_hash
                or (item.tenant.org_id, item.tenant.project_id) != scope.key
                or item.receipt_id != row["receipt_id"] or item.fulfillment_id != row["fulfillment_id"]
                or item.requirement_ref.resource_id != row["requirement_id"]
                or item.requirement_ref.revision != int(row["requirement_revision"])
                or item.requirement_ref.content_hash != "sha256:" + str(row["requirement_hash"]).strip()
                or item.status.value != row["status"] or item.created_by != row["created_by"]
                or item.cutoff_at != row["cutoff_at"] or item.fulfilled_at != row["fulfilled_at"]
                or [r.model_dump(by_alias=True) for r in item.artifact_refs] != row["artifact_refs"]
                or item.source_readiness_ref.model_dump(by_alias=True) != row["source_readiness_ref"]):
            raise DataFulfillmentValidationError("fulfillment readback content hash drifted")
        return item

    def bind(self, scope: TenantScope, actor: str, idempotency_key: str, item: DataFulfillmentReceiptRecord) -> DataFulfillmentBindResult:
        if scope.key != (item.tenant.org_id, item.tenant.project_id): raise DataFulfillmentValidationError("tenant scope mismatch")
        if actor != item.created_by or not actor: raise DataFulfillmentValidationError("actor must match createdBy")
        if not idempotency_key.strip() or len(idempotency_key) > 200: raise DataFulfillmentValidationError("idempotency key is invalid")
        if item.content_hash != canonical_fulfillment_content_hash(item): raise DataFulfillmentValidationError("content hash mismatch")
        # Preserve the exact datetime spelling used by the existing content hash.
        payload = json.loads(json.dumps(item.model_dump(mode="python", by_alias=True), default=str))
        request_hash = _hash({"operation": "fulfillment.bind", "receipt": payload})
        params = (json.dumps(payload, ensure_ascii=False), idempotency_key, request_hash)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute("SELECT bound_receipt_id,result_content_hash,replayed FROM data_fulfillment_bind_ar2_008(%s::jsonb,%s,%s)", params).fetchone()
                if row is None: raise DataFulfillmentStoreError("binding returned no result")
                conn.commit()
        except psycopg.Error as exc:
            if exc.sqlstate == "DF002": raise DataFulfillmentIdempotencyConflict("idempotency conflict") from exc
            if exc.sqlstate in {"DF001", "23505"}: raise DataFulfillmentConflict("fulfillment binding conflict") from exc
            raise
        content_hash = f"sha256:{str(row['result_content_hash']).strip()}"
        return DataFulfillmentBindResult(str(row["bound_receipt_id"]), content_hash, bool(row["replayed"]))
