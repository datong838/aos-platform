"""Single owner projector from authoritative e-commerce Outbox to compatibility views."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PROJECTOR_ACTOR = "ecom-projector-v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verify_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    if digest != row["payload_hash"]:
        raise RuntimeError("PROJECTION_PAYLOAD_HASH_MISMATCH")
    if payload.get("schemaVersion") != 1:
        raise RuntimeError("PROJECTION_SCHEMA_UNSUPPORTED")
    return payload


def _project_object(conn: Any, scope: TenantScope, payload: dict[str, Any]) -> None:
    record = payload["record"]
    object_type = str(record.get("objectType") or record["object_type"])
    identity = record["identity"]
    object_id = str(identity.get("externalId") or identity["external_id"])
    is_deleted = bool(record.get("isDeleted", record.get("is_deleted", False)))
    if is_deleted:
        conn.execute(
            "DELETE FROM graph_edge WHERE org_id=%s AND project_id=%s "
            "AND ((src_type=%s AND src_id=%s) OR (dst_type=%s AND dst_id=%s))",
            (*scope.key, object_type, object_id, object_type, object_id),
        )
        conn.execute(
            "DELETE FROM obj_instance WHERE org_id=%s AND project_id=%s "
            "AND object_type=%s AND object_id=%s",
            (*scope.key, object_type, object_id),
        )
        return
    props = dict(record.get("properties") or {})
    props["_sourceIdentity"] = identity
    props["_sourceUpdatedAt"] = record.get("sourceUpdatedAt") or record["source_updated_at"]
    props["_schemaVersion"] = record.get("schemaVersion", record.get("schema_version", 1))
    conn.execute(
        "INSERT INTO meta_object_type (id,name,description,published,properties) "
        "VALUES (%s,%s,%s,TRUE,'{}'::jsonb) ON CONFLICT (id) DO NOTHING",
        (object_type, object_type, "e-commerce authoritative projection"),
    )
    conn.execute(
        "INSERT INTO obj_instance (org_id,project_id,object_type,object_id,props) "
        "VALUES (%s,%s,%s,%s,%s::jsonb) "
        "ON CONFLICT (org_id,project_id,object_type,object_id) DO UPDATE SET props=EXCLUDED.props",
        (*scope.key, object_type, object_id, json.dumps(props, ensure_ascii=False)),
    )


def _project_link(conn: Any, scope: TenantScope, payload: dict[str, Any]) -> None:
    record = payload["record"]
    source = record["source"]
    target = record["target"]
    values = (
        *scope.key,
        str(record.get("sourceType") or record["source_type"]),
        str(source.get("externalId") or source["external_id"]),
        str(record.get("linkType") or record["link_type"]),
        str(record.get("targetType") or record["target_type"]),
        str(target.get("externalId") or target["external_id"]),
    )
    if bool(record.get("isDeleted", record.get("is_deleted", False))):
        conn.execute(
            "DELETE FROM graph_edge WHERE org_id=%s AND project_id=%s "
            "AND src_type=%s AND src_id=%s AND rel=%s AND dst_type=%s AND dst_id=%s",
            values,
        )
        return
    conn.execute(
        "INSERT INTO graph_edge (org_id,project_id,src_type,src_id,rel,dst_type,dst_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (org_id,project_id,src_type,src_id,rel,dst_type,dst_id) DO NOTHING",
        values,
    )


def projection_order_lock_key(scope: TenantScope) -> int:
    """Stable tenant ordering lock shared by all authoritative projectors."""
    material = _canonical_json(['ecom-projector-order-v1', *scope.key]).encode('utf-8')
    return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big', signed=True)


def project_pending(scope: TenantScope, *, limit: int = 500) -> dict[str, int]:
    """Project one leased batch atomically; safe for concurrent workers and replay."""
    if limit < 1 or limit > 5000:
        raise ValueError("limit must be between 1 and 5000")
    projected = 0
    with connect(scope) as conn:
        # Row leases alone allow a later event to overtake a paused earlier
        # event for the same object. Serialize projector transactions per tenant.
        lock_key = projection_order_lock_key(scope)
        locked = conn.execute('SELECT pg_try_advisory_xact_lock(%s) AS acquired', (lock_key,)).fetchone()['acquired']
        if not locked:
            pending = conn.execute(
                "SELECT count(*) AS pending FROM projection_outbox WHERE org_id=%s AND project_id=%s "
                "AND event_source='authoritative_store' AND projected=FALSE", scope.key,
            ).fetchone()['pending']
            return {'projected':0,'pending':int(pending)}
        conn.execute("SELECT set_config('aos.projection_actor', %s, true)", (PROJECTOR_ACTOR,))
        rows = conn.execute(
            "SELECT * FROM projection_outbox WHERE org_id=%s AND project_id=%s "
            "AND event_source='authoritative_store' AND projected=FALSE "
            "ORDER BY input_revision,outbox_id FOR UPDATE SKIP LOCKED LIMIT %s",
            (*scope.key, limit),
        ).fetchall()
        for row in rows:
            payload = _verify_payload(row)
            if payload.get("entityKind") == "object":
                _project_object(conn, scope, payload)
            elif payload.get("entityKind") == "link":
                _project_link(conn, scope, payload)
            else:
                raise RuntimeError("PROJECTION_ENTITY_KIND_UNSUPPORTED")
            conn.execute(
                "UPDATE projection_outbox SET projected=TRUE,projected_at=now(),projection_error=NULL "
                "WHERE org_id=%s AND project_id=%s AND outbox_id=%s",
                (*scope.key, row["outbox_id"]),
            )
            projected += 1
        pending = conn.execute(
            "SELECT count(*) AS pending FROM projection_outbox WHERE org_id=%s AND project_id=%s "
            "AND event_source='authoritative_store' AND projected=FALSE", scope.key,
        ).fetchone()['pending']
    return {"projected": projected, "pending": int(pending)}


def project_until_caught_up(scope: TenantScope, *, deadline: float, cancel_event=None) -> dict[str, int]:
    """Drain committed batches within the executor deadline before Dataset success."""
    def check():
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('PROJECTION_CANCELLED')
        if time.monotonic() >= deadline:
            raise RuntimeError('PROJECTION_DEADLINE_EXCEEDED')
    total = 0
    while True:
        check()
        result = project_pending(scope)
        check()
        if (type(result) is not dict or any(type(result.get(key)) is not int or result[key] < 0
                                          for key in ('projected','pending'))):
            raise RuntimeError('PROJECTION_RESULT_INVALID')
        total += result['projected']
        if result['pending'] == 0:
            return {'projected':total,'pending':0}
        if result['projected'] == 0:
            delay = min(0.05,max(0,deadline-time.monotonic()))
            if cancel_event is not None:
                cancel_event.wait(delay)
            else:
                time.sleep(delay)
