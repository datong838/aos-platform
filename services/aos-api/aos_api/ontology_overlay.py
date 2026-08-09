"""Installation-bound organization ontology overlay service."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

_ETAG_RE = re.compile(r'^"ontology-overlay-v1:(\d+):([0-9a-f]{64})"$')


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _base_schema(conn: Any, target_kind: str, target_id: str) -> tuple[dict[str, Any], str]:
    if target_kind == "ObjectType":
        from aos_api.ecom_core_models import CORE_OBJECT_TYPES

        if target_id not in CORE_OBJECT_TYPES:
            raise ApiError(code="ONTOLOGY_TARGET_NOT_CONTRIBUTED", message="target is not contributed by ecommerce core", status_code=409)
        row = conn.execute(
            "SELECT id,name,description,published,properties FROM meta_object_type WHERE id=%s",
            (target_id,),
        ).fetchone()
        if row is None:
            raise ApiError(code="NOT_FOUND", message="object type not found", status_code=404)
        schema = dict(row)
    elif target_kind == "LinkType":
        from aos_api.ecom_core_models import CORE_LINK_TYPES

        if target_id not in CORE_LINK_TYPES:
            raise ApiError(code="ONTOLOGY_TARGET_NOT_CONTRIBUTED", message="target is not contributed by ecommerce core", status_code=409)
        row = conn.execute(
            "SELECT id,name,src_type,dst_type,rel,cardinality,description,published "
            "FROM meta_link_type WHERE id=%s OR rel=%s ORDER BY id LIMIT 1",
            (target_id, target_id),
        ).fetchone()
        if row is None:
            raise ApiError(code="NOT_FOUND", message="link type not found", status_code=404)
        schema = dict(row)
    else:
        raise ApiError(code="VALIDATION", message="unsupported target kind", status_code=422)
    return schema, canonical_hash(schema)


def _lock_installation(conn: Any, scope: TenantScope, installation_pk: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT bi.installation_pk,bi.active_revision,bir.overlay_revision,
               bir.composition_pk,bir.lock_revision,bir.lock_hash,
               bil.lock_hash AS stored_lock_hash,bil.lock_payload
          FROM bundle_installation bi
          JOIN bundle_installation_revision bir
            ON bir.org_id=bi.org_id AND bir.project_id=bi.project_id
           AND bir.installation_pk=bi.installation_pk AND bir.revision=bi.active_revision
           AND bir.state='active'
          JOIN bundle_composition_lock bil
            ON bil.org_id=bir.org_id AND bil.project_id=bir.project_id
           AND bil.composition_pk=bir.composition_pk AND bil.revision=bir.lock_revision
         WHERE bi.org_id=%s AND bi.project_id=%s AND bi.installation_pk=%s
         FOR UPDATE OF bi
        """,
        (*scope.key, installation_pk),
    ).fetchone()
    if row is None:
        raise ApiError(code="ONTOLOGY_INSTALLATION_NOT_ACTIVE", message="active installation not found", status_code=409)
    if row["lock_hash"] != row["stored_lock_hash"]:
        raise ApiError(code="ONTOLOGY_INSTALLATION_LOCK_HASH_MISMATCH", message="installation lock verification failed", status_code=409)
    resolved = (row["lock_payload"] or {}).get("resolved") or []
    if not any(isinstance(item, dict) and item.get("id") == "domain.ecommerce.core" for item in resolved):
        raise ApiError(code="ONTOLOGY_TARGET_NOT_CONTRIBUTED", message="installation does not contribute ecommerce ontology", status_code=409)
    return dict(row)


def _expected_revision(if_match: str) -> int:
    if if_match == '"0"':
        return 0
    match = _ETAG_RE.fullmatch(if_match)
    if match is None:
        raise ApiError(code="ONTOLOGY_OVERLAY_IF_MATCH_INVALID", message="If-Match must be a returned ontology overlay ETag", status_code=400)
    return int(match.group(1))


def _validate_override(body: dict[str, Any], base_schema: dict[str, Any]) -> None:
    if body["mode"] != "override":
        return
    if "properties" in base_schema:
        base_names = {
            str(prop.get("name") or prop.get("id"))
            for prop in (base_schema.get("properties") or [])
            if isinstance(prop, dict) and (prop.get("name") or prop.get("id"))
        }
    else:
        base_names = set()
    extended = set((body.get("extended_properties") or {}).keys())
    overlap = base_names & extended
    if overlap:
        raise ApiError(
            code="ONTOLOGY_OVERLAY_PROPERTY_CONFLICT",
            message="extended properties cannot replace base properties",
            status_code=422,
            details={"properties": sorted(overlap)},
        )
    visible = set(body.get("visible_properties") or [])
    unknown = visible - base_names - extended
    if unknown:
        raise ApiError(
            code="ONTOLOGY_OVERLAY_VISIBLE_PROPERTY_UNKNOWN",
            message="visible properties must exist in the composed schema",
            status_code=422,
            details={"properties": sorted(unknown)},
        )


def put_overlay(
    conn: Any,
    scope: TenantScope,
    *,
    installation_pk: str,
    target_kind: str,
    target_id: str,
    body: dict[str, Any],
    if_match: str,
    idempotency_key: str,
    actor: str,
) -> tuple[dict[str, Any], str]:
    expected = _expected_revision(if_match)
    normalized = dict(body)
    if normalized["mode"] == "inherit":
        normalized.update(display_name=None, visible_properties=None, extended_properties={}, policies=None)
    request_hash = canonical_hash({
        "scope": scope.key, "installationPk": installation_pk,
        "targetKind": target_kind, "targetId": target_id,
        "ifMatch": if_match, "actor": actor, "body": normalized,
    })
    receipt = conn.execute(
        "SELECT request_hash,response_etag,result_json FROM ontology_overlay_receipt "
        "WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s",
        (*scope.key, idempotency_key),
    ).fetchone()
    if receipt is not None:
        if receipt["request_hash"] != request_hash:
            raise ApiError(code="IDEMPOTENCY_CONFLICT", message="idempotency key was used by another request", status_code=409)
        return dict(receipt["result_json"]), receipt["response_etag"]

    installation = _lock_installation(conn, scope, installation_pk)
    base_schema, base_hash = _base_schema(conn, target_kind, target_id)
    _validate_override(normalized, base_schema)
    active = conn.execute(
        "SELECT * FROM ontology_overlay WHERE org_id=%s AND workspace_id=%s "
        "AND installation_pk=%s AND target_kind=%s AND target_id=%s AND is_active "
        "FOR UPDATE",
        (*scope.key, installation_pk, target_kind, target_id),
    ).fetchone()
    current = int(active["ontology_revision"]) if active else 0
    if current != expected:
        raise ApiError(
            code="ONTOLOGY_OVERLAY_CAS_CONFLICT",
            message="ontology overlay revision changed",
            status_code=412,
            details={"expected": expected, "actual": current},
        )
    if active is not None and active["base_schema_sha256"] != base_hash:
        raise ApiError(code="ONTOLOGY_BASE_SCHEMA_DRIFT", message="base schema changed; rebuild the overlay", status_code=409)

    revision = current + 1
    if active is not None:
        conn.execute(
            "UPDATE ontology_overlay SET is_active=FALSE,updated_at=now() "
            "WHERE org_id=%s AND workspace_id=%s AND installation_pk=%s "
            "AND target_kind=%s AND target_id=%s AND ontology_revision=%s",
            (*scope.key, installation_pk, target_kind, target_id, current),
        )
    conn.execute(
        """
        INSERT INTO ontology_overlay(
          org_id,workspace_id,installation_pk,target_kind,target_id,mode,
          display_name,visible_properties,extended_properties,policies,
          base_schema_sha256,ontology_revision,is_active,created_by
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,TRUE,%s)
        """,
        (
            *scope.key, installation_pk, target_kind, target_id, normalized["mode"],
            normalized.get("display_name"),
            json.dumps(normalized["visible_properties"]) if normalized.get("visible_properties") is not None else None,
            json.dumps(normalized.get("extended_properties") or {}),
            json.dumps(normalized["policies"]) if normalized.get("policies") is not None else None,
            base_hash, revision, actor,
        ),
    )
    etag = f'"ontology-overlay-v1:{revision}:{base_hash}"'
    result = {
        "installationPk": str(installation["installation_pk"]),
        "installationRevision": int(installation["active_revision"]),
        "installationOverlayRevision": installation["overlay_revision"],
        "targetKind": target_kind, "targetId": target_id,
        "ontologyRevision": revision, "baseSchemaSha256": base_hash,
        "mode": normalized["mode"], "displayName": normalized.get("display_name"),
        "visibleProperties": normalized.get("visible_properties"),
        "extendedProperties": normalized.get("extended_properties") or {},
        "policies": normalized.get("policies"), "baseSchema": base_schema,
        "createdBy": actor,
    }
    conn.execute(
        """
        INSERT INTO ontology_overlay_receipt(
          org_id,workspace_id,idempotency_key,request_hash,installation_pk,target_kind,target_id,
          expected_ontology_revision,resulting_ontology_revision,base_schema_sha256,actor,response_etag,result_json
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (*scope.key, idempotency_key, request_hash, installation_pk, target_kind, target_id,
         expected, revision, base_hash, actor, etag, json.dumps(result, ensure_ascii=False)),
    )
    return result, etag


def list_overlays(conn: Any, scope: TenantScope, installation_pk: str, *, active_only: bool) -> list[dict[str, Any]]:
    suffix = " AND is_active" if active_only else ""
    rows = conn.execute(
        "SELECT * FROM ontology_overlay WHERE org_id=%s AND workspace_id=%s AND installation_pk=%s"
        + suffix + " ORDER BY target_kind,target_id,ontology_revision DESC",
        (*scope.key, installation_pk),
    ).fetchall()
    return [dict(row) for row in rows]
