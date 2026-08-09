"""Single owner projector from authoritative e-commerce Outbox to compatibility views."""

from __future__ import annotations

import hashlib
import json
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


def project_pending(scope: TenantScope, *, limit: int = 500) -> dict[str, int]:
    """Project one leased batch atomically; safe for concurrent workers and replay."""
    if limit < 1 or limit > 5000:
        raise ValueError("limit must be between 1 and 5000")
    projected = 0
    with connect(scope) as conn:
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
    return {"projected": projected, "pending": max(0, len(rows) - projected)}
