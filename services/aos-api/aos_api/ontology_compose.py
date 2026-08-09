"""Installation-aware ontology composition boundary (base mode)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from aos_api.ecom_core_models import CORE_LINK_TYPES, CORE_OBJECT_TYPES
from aos_api.tenant_scope import TenantScope


def active_ecommerce_installation(conn: Any, scope: TenantScope) -> dict[str, Any] | None:
    """Resolve the latest active integration binding and verify its frozen lock."""
    row = conn.execute(
        """
        SELECT i.instance_pk, ir.installation_pk, ir.installation_revision,
               ir.composition_pk, ir.lock_revision, ir.lock_hash,
               ir.overlay_revision AS installation_overlay_revision,
               bil.lock_payload, bil.lock_hash AS stored_lock_hash
          FROM integration_instance i
          JOIN integration_instance_revision ir
            ON ir.org_id=i.org_id AND ir.project_id=i.project_id
           AND ir.instance_pk=i.instance_pk AND ir.revision=i.current_revision
          JOIN bundle_installation bi
            ON bi.org_id=ir.org_id AND bi.project_id=ir.project_id
           AND bi.installation_pk=ir.installation_pk
           AND bi.active_revision=ir.installation_revision
          JOIN bundle_installation_revision bir
            ON bir.org_id=bi.org_id AND bir.project_id=bi.project_id
           AND bir.installation_pk=bi.installation_pk
           AND bir.revision=bi.active_revision AND bir.state='active'
          JOIN bundle_composition_lock bil
            ON bil.org_id=ir.org_id AND bil.project_id=ir.project_id
           AND bil.composition_pk=ir.composition_pk AND bil.revision=ir.lock_revision
         WHERE i.org_id=%s AND i.project_id=%s
         ORDER BY i.updated_at DESC, i.instance_pk DESC
         LIMIT 1
        """,
        scope.key,
    ).fetchone()
    if row is None:
        return None
    if row["lock_hash"] != row["stored_lock_hash"]:
        raise RuntimeError("ONTOLOGY_INSTALLATION_LOCK_HASH_MISMATCH")
    resolved = (row["lock_payload"] or {}).get("resolved") or []
    if not any(
        item.get("id") == "domain.ecommerce.core"
        for item in resolved
        if isinstance(item, dict)
    ):
        return None
    return {
        "installation_pk": str(row["installation_pk"]),
        "installation_revision": int(row["installation_revision"]),
        "installation_overlay_revision": row["installation_overlay_revision"],
        "lock_hash": row["lock_hash"],
        "ontology_revision": 0,
        "ontology_overlay_set_hash": "sha256:" + "0" * 64,
        "composed_schema_etag": f"composed-schema-v1:{row['lock_hash']}",
    }


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _active_overlays(conn: Any, scope: TenantScope, installation_pk: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM ontology_overlay WHERE org_id=%s AND workspace_id=%s "
        "AND installation_pk=%s AND is_active "
        "ORDER BY target_kind,target_id,ontology_revision",
        (*scope.key, installation_pk),
    ).fetchall()
    return [dict(row) for row in rows]


def _finish_composition(installation: dict[str, Any], overlays: list[dict[str, Any]]) -> None:
    overlay_contract = [
        {
            "targetKind": row["target_kind"], "targetId": row["target_id"],
            "ontologyRevision": row["ontology_revision"], "mode": row["mode"],
            "baseSchemaSha256": row["base_schema_sha256"],
            "displayName": row["display_name"],
            "visibleProperties": row["visible_properties"],
            "extendedProperties": row["extended_properties"], "policies": row["policies"],
        }
        for row in overlays
    ]
    set_hash = "sha256:" + _canonical_hash(overlay_contract)
    installation["ontology_revision"] = max(
        (int(row["ontology_revision"]) for row in overlays), default=0
    )
    installation["ontology_overlay_set_hash"] = set_hash
    installation["base_schema_sha256"] = {
        f"{row['target_kind']}:{row['target_id']}": row["base_schema_sha256"]
        for row in overlays
    }
    installation["composed_schema_etag"] = "composed-schema-v1:sha256:" + _canonical_hash(
        {
            "installationPk": installation["installation_pk"],
            "installationRevision": installation["installation_revision"],
            "installationOverlayRevision": installation["installation_overlay_revision"],
            "lockHash": installation["lock_hash"],
            "ontologyOverlaySetHash": set_hash,
        }
    )


def _verify_base(row: dict[str, Any], overlay: dict[str, Any], *, kind: str) -> None:
    if kind == "ObjectType":
        schema = {key: row[key] for key in ("id", "name", "description", "published", "properties")}
    else:
        schema = {
            key: row[key]
            for key in ("id", "name", "src_type", "dst_type", "rel", "cardinality", "description", "published")
        }
    if _canonical_hash(schema) != overlay["base_schema_sha256"]:
        from aos_api.errors import ApiError

        raise ApiError(
            code="ONTOLOGY_BASE_SCHEMA_DRIFT",
            message="base schema changed; rebuild the organization overlay",
            status_code=409,
        )


def _property_rows(value: Any) -> list[dict[str, Any]]:
    """Normalize legacy dict-backed schemas to the public property-array contract."""
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [
            {"name": name, **(dict(spec) if isinstance(spec, dict) else {})}
            for name, spec in value.items()
        ]
    return []


def filter_object_type_rows(
    conn: Any, scope: TenantScope, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    installation = active_ecommerce_installation(conn, scope)
    if installation is not None:
        overlays = _active_overlays(conn, scope, installation["installation_pk"])
        by_id = {
            row["target_id"]: row for row in overlays if row["target_kind"] == "ObjectType"
        }
        composed: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            overlay = by_id.get(row["id"])
            if overlay is not None:
                _verify_base(row, overlay, kind="ObjectType")
                if overlay["mode"] == "override":
                    row["name"] = overlay["display_name"]
                    extended = [
                        {"name": name, **spec}
                        for name, spec in (overlay["extended_properties"] or {}).items()
                    ]
                    properties = _property_rows(row.get("properties")) + extended
                    if overlay["visible_properties"] is not None:
                        visible = set(overlay["visible_properties"])
                        properties = [
                            prop for prop in properties
                            if isinstance(prop, dict) and (prop.get("name") or prop.get("id")) in visible
                        ]
                    row["properties"] = properties
            row["properties"] = _property_rows(row.get("properties"))
            composed.append(row)
        _finish_composition(installation, overlays)
        return composed, installation
    visible = [dict(row) for row in rows if row["id"] not in CORE_OBJECT_TYPES]
    for row in visible:
        row["properties"] = _property_rows(row.get("properties"))
    return visible, None


def filter_link_type_rows(
    conn: Any, scope: TenantScope, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    installation = active_ecommerce_installation(conn, scope)
    if installation is not None:
        overlays = _active_overlays(conn, scope, installation["installation_pk"])
        by_id = {
            row["target_id"]: row for row in overlays if row["target_kind"] == "LinkType"
        }
        composed: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            overlay = by_id.get(row["id"]) or by_id.get(row.get("rel"))
            if overlay is not None:
                _verify_base(row, overlay, kind="LinkType")
                if overlay["mode"] == "override":
                    row["name"] = overlay["display_name"]
            composed.append(row)
        _finish_composition(installation, overlays)
        return composed, installation
    owned = set(CORE_LINK_TYPES)
    return [row for row in rows if row["id"] not in owned and row.get("rel") not in owned], None


def assert_object_type_visible(conn: Any, scope: TenantScope, object_type: str) -> None:
    if object_type in CORE_OBJECT_TYPES and active_ecommerce_installation(conn, scope) is None:
        from aos_api.errors import ApiError

        raise ApiError(code="NOT_FOUND", message="object type is not installed", status_code=404)


def assert_link_type_visible(conn: Any, scope: TenantScope, link_type: str) -> None:
    if link_type in CORE_LINK_TYPES and active_ecommerce_installation(conn, scope) is None:
        from aos_api.errors import ApiError

        raise ApiError(code="NOT_FOUND", message="link type is not installed", status_code=404)
