"""Immutable snapshots of existing SourceReadiness decisions, not a second evaluator."""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_readiness_contracts import (
    ExactResourceRef, SOURCE_READINESS_SCHEMA_VERSION, SourceReadinessEnvelope,
)
from aos_api.tenant_scope import TenantScope

AUTHORITY = "postgres:source_readiness_receipt"


def _canonical_times(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("readiness snapshot times require timezone")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(value, dict):
        return {key: _canonical_times(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_times(item) for item in value]
    return value


def canonical_snapshot(envelope: SourceReadinessEnvelope) -> tuple[dict[str, Any], str]:
    # Revalidate model_copy callers as well as normally constructed DTOs.
    item = SourceReadinessEnvelope.model_validate(envelope.model_dump(by_alias=True))
    if item.receipt_ref is not None:
        raise ValueError("new readiness snapshot must not claim an existing receipt")
    if item.schema_version != SOURCE_READINESS_SCHEMA_VERSION or any(
        source.schema_version != SOURCE_READINESS_SCHEMA_VERSION for source in item.sources
    ):
        raise ValueError("unsupported readiness schema")
    body = _canonical_times(item.model_dump(by_alias=True, mode="python"))
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(raw.encode("utf-8")) > 2_000_000:
        raise ValueError("readiness snapshot exceeds size limit")
    return body, hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SourceReadinessReceiptStore:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("readiness store requires host transaction and tenant scope")
        self._transaction, self._scope = transaction, scope

    def _decode(self, row: Any, digest: str) -> SourceReadinessEnvelope:
        if row is None or not isinstance(row.get("authority"), dict) or row.get("content_hash") != digest:
            raise ValueError("readiness receipt identity drifted")
        item = SourceReadinessEnvelope.model_validate(row["authority"])
        body, actual_hash = canonical_snapshot(item)
        if ((item.tenant.org_id, item.tenant.project_id) != self._scope.key
                or actual_hash != digest or body != row["authority"]):
            raise ValueError("readiness receipt tenant or canonical body drifted")
        ref = ExactResourceRef(resource_type="SourceReadinessEnvelope", resource_id="readiness-" + digest,
                               revision="1", content_hash=digest, authority=AUTHORITY)
        return item.model_copy(update={"receipt_ref": ref})

    def put(self, envelope: SourceReadinessEnvelope) -> SourceReadinessEnvelope:
        body, digest = canonical_snapshot(envelope)
        if (envelope.tenant.org_id, envelope.tenant.project_id) != self._scope.key:
            raise ValueError("readiness snapshot tenant mismatch")
        row = self._transaction.execute(
            "SELECT authority,content_hash,replayed FROM source_readiness_snapshot_put_ar2_009(%s::jsonb,%s)",
            (json.dumps(body, ensure_ascii=False, allow_nan=False), digest),
        ).fetchone()
        result = self._decode(row, digest)
        if row["authority"] != body:
            raise ValueError("readiness snapshot persistence drifted")
        return result

    def read_exact(self, ref: ExactResourceRef) -> SourceReadinessEnvelope | None:
        if (ref.resource_type != "SourceReadinessEnvelope" or ref.revision != "1"
                or ref.authority != AUTHORITY or ref.resource_id != "readiness-" + ref.content_hash):
            raise ValueError("canonical readiness receipt reference required")
        row = self._transaction.execute("""SELECT authority,content_hash FROM source_readiness_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s""", (*self._scope.key, ref.resource_id)).fetchone()
        return None if row is None else self._decode(row, ref.content_hash)
