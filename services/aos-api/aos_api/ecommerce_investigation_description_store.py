"""Persisted, tenant-scoped receipts for read-only investigation descriptions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping
from uuid import UUID, uuid5

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


DESCRIPTION_NAMESPACE = UUID("2da59db9-653d-4995-8516-a1bd6fd08dc8")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class InvestigationDescriptionConflict(RuntimeError):
    """The persisted description no longer matches its immutable identity."""


def canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def deterministic_receipt_id(scope: TenantScope, idempotency_key: str) -> UUID:
    return uuid5(DESCRIPTION_NAMESPACE, "\x1f".join((*scope.key, idempotency_key.strip())))


def receipt_ref(receipt_id: UUID, content_hash: str) -> dict[str, Any]:
    return {
        "resourceType": "InvestigationDescriptionReceipt",
        "resourceId": str(receipt_id),
        "revision": 1,
        "contentHash": content_hash,
        "receiptId": str(receipt_id),
    }


@dataclass(frozen=True, slots=True)
class InvestigationDescriptionRecord:
    receipt_ref: dict[str, Any]
    authority: dict[str, Any]
    replayed: bool


class InvestigationDescriptionStore:
    """Write and exactly reread one immutable domain receipt in the host transaction."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("description store requires a host transaction and tenant scope")
        self._transaction = transaction
        self._scope = scope

    def put(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        authority: Mapping[str, Any],
        created_at: datetime,
    ) -> InvestigationDescriptionRecord:
        key = idempotency_key.strip() if type(idempotency_key) is str else ""
        if not 1 <= len(key) <= 200 or not _SHA256.fullmatch(request_hash):
            raise ValueError("description identity is invalid")
        if not isinstance(created_at, datetime) or created_at.utcoffset() is None:
            raise ValueError("description time must include timezone")
        payload = deepcopy(dict(authority))
        if not payload or payload.get("schemaVersion") != "aos.ecommerce.investigation-description/v1":
            raise ValueError("description authority is invalid")
        receipt_id = deterministic_receipt_id(self._scope, key)
        if payload.get("receiptId") != str(receipt_id):
            raise ValueError("description receiptId is not deterministic")
        content_hash = canonical_hash(payload)
        row = self._transaction.execute(
            """SELECT authority,replayed
                 FROM ecommerce_investigation_description_put_ar2_006(%s,%s,%s,%s,%s::jsonb,%s)""",
            (
                key,
                request_hash,
                receipt_id,
                content_hash,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        ).fetchone()
        if row is None or type(row.get("authority")) is not dict or type(row.get("replayed")) is not bool:
            raise InvestigationDescriptionConflict("description persistence returned invalid data")
        persisted = deepcopy(row["authority"])
        if persisted != payload or canonical_hash(persisted) != content_hash:
            raise InvestigationDescriptionConflict("description persistence drifted")
        return InvestigationDescriptionRecord(
            receipt_ref=receipt_ref(receipt_id, content_hash),
            authority=persisted,
            replayed=row["replayed"],
        )

    def read(self, receipt_id: UUID) -> InvestigationDescriptionRecord | None:
        if type(receipt_id) is not UUID:
            raise TypeError("description receipt lookup requires UUID")
        row = self._transaction.execute(
            """SELECT authority,content_hash FROM ecommerce_investigation_description_receipt
                 WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (*self._scope.key, receipt_id),
        ).fetchone()
        if row is None:
            return None
        authority = deepcopy(row["authority"])
        content_hash = str(row["content_hash"])
        if type(authority) is not dict or canonical_hash(authority) != content_hash:
            raise InvestigationDescriptionConflict("stored description content hash drifted")
        return InvestigationDescriptionRecord(
            receipt_ref=receipt_ref(receipt_id, content_hash),
            authority=authority,
            replayed=True,
        )


__all__ = [
    "InvestigationDescriptionConflict",
    "InvestigationDescriptionRecord",
    "InvestigationDescriptionStore",
    "canonical_hash",
    "deterministic_receipt_id",
    "receipt_ref",
]
