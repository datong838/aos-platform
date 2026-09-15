"""Read-only product event integrity check for rows read by a trusted Owner.

This does not authenticate caller-supplied rows, grant admission, acknowledge
the projection outbox, or prove source freshness. Never expose it as a write
authorization endpoint. The consumer must separately validate current authority.
"""

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ProductSourceEvent:
    org_id: str
    project_id: str
    source_event_id: str
    input_revision: int
    outbox_id: int
    payload_hash: str
    authority_tx_id: str
    platform: str
    shop_or_marketplace_id: str
    object_type: str
    external_id: str
    deleted: bool


def validate_product_source_event(
    row: Mapping[str, Any], *, org_id: str, project_id: str
) -> ProductSourceEvent:
    """Return immutable metadata only; malformed input raises a fixed safe code."""
    def require(condition: bool, code: str) -> None:
        if not condition:
            raise ValueError("PRODUCT_SOURCE_EVENT_" + code)

    def text(value: Any) -> bool:
        return isinstance(value, str) and bool(value) and value.strip() == value

    require(text(org_id) and text(project_id), "SCOPE_INVALID")
    require(isinstance(row, Mapping), "ROW_INVALID")
    require((row.get("org_id"), row.get("project_id"), row.get("workspace_id"))
            == (org_id, project_id, project_id), "SCOPE_MISMATCH")
    require(row.get("event_source") == "authoritative_store", "ORIGIN_INVALID")
    for name in ("event_key", "payload_hash", "authority_tx_id"):
        require(isinstance(row.get(name), str)
                and re.fullmatch(r"[0-9a-f]{64}", row[name]) is not None, "HASH_INVALID")
    for name in ("input_revision", "outbox_id"):
        require(type(row.get(name)) is int and row[name] > 0, "REVISION_INVALID")
    require(row.get("object_type") in ("Product", "ProductSku"), "TYPE_INVALID")
    change = row.get("change_kind")
    require(change in ("objects_written", "objects_tombstoned"), "CHANGE_INVALID")
    identity = {
        "org_id": org_id, "workspace_id": project_id,
        "platform": row.get("platform"),
        "shop_or_marketplace_id": row.get("shop_or_marketplace_id"),
        "external_id": row.get("external_id"),
    }
    require(all(text(value) for value in identity.values()), "IDENTITY_INVALID")
    payload = row.get("payload")
    require(type(payload) is dict, "PAYLOAD_INVALID")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("PRODUCT_SOURCE_EVENT_PAYLOAD_INVALID") from None
    require(hashlib.sha256(encoded).hexdigest() == row["payload_hash"], "HASH_MISMATCH")
    require(type(payload.get("schemaVersion")) is int and payload["schemaVersion"] == 1,
            "SCHEMA_INVALID")
    require(payload.get("entityKind") == "object" and payload.get("changeKind") == change,
            "ENVELOPE_MISMATCH")
    record = payload.get("record")
    require(type(record) is dict, "RECORD_INVALID")
    require(payload.get("objectType") == record.get("object_type") == row["object_type"],
            "TYPE_MISMATCH")
    require(payload.get("identity") == record.get("identity") == identity, "IDENTITY_MISMATCH")
    deleted = change == "objects_tombstoned"
    require(record.get("is_deleted") is deleted, "DELETION_MISMATCH")
    return ProductSourceEvent(
        org_id=org_id, project_id=project_id, source_event_id=row["event_key"],
        input_revision=row["input_revision"], outbox_id=row["outbox_id"],
        payload_hash=row["payload_hash"], authority_tx_id=row["authority_tx_id"],
        platform=identity["platform"], shop_or_marketplace_id=identity["shop_or_marketplace_id"],
        object_type=row["object_type"], external_id=identity["external_id"], deleted=deleted,
    )
