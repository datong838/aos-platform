from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.constitution import lint_object_type
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.marking import (
    apply_field_redaction,
    can_access_object,
    ensure_object_access,
)
from aos_api.ot_detail_meta import build_ot_detail_meta
from aos_api.ontology_explorer_contracts import GraphQueryDTO
from aos_api.ontology_display_names import build_object_display_projection
from aos_api.ontology_graph_query import get_authoritative_graph_service
from aos_api.oidc import allow_dev
from aos_api.tenant_scope import TenantScope

router = APIRouter(tags=["ontology"])
log = get_logger("aos-api.ontology")


_OBJECT_SORT_ALLOWLIST: dict[str, frozenset[str]] = {
    "Order": frozenset({"createdAt"}),
}
_OBJECT_DEFAULT_SORTS: dict[str, tuple[str, str]] = {
    "Order": ("createdAt", "desc"),
}


def _resolve_object_sort(
    object_type: str,
    sort_by: str | None,
    sort_direction: str | None,
) -> tuple[str, str] | None:
    """Resolve an allow-listed global object sort without dynamic SQL."""
    if sort_by is None and sort_direction is None:
        return _OBJECT_DEFAULT_SORTS.get(object_type)
    effective_by = sort_by or (_OBJECT_DEFAULT_SORTS.get(object_type) or (None, None))[0]
    effective_direction = (sort_direction or "asc").lower()
    if (
        not effective_by
        or effective_by not in _OBJECT_SORT_ALLOWLIST.get(object_type, frozenset())
        or effective_direction not in {"asc", "desc"}
    ):
        raise ApiError(
            code="OBJECT_SORT_INVALID",
            message=f"unsupported sort for {object_type}",
            status_code=422,
        )
    return effective_by, effective_direction


def _object_sort_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sort_object_items(
    items: list[dict[str, Any]],
    sort: tuple[str, str] | None,
) -> tuple[list[dict[str, Any]], int]:
    """Sort the complete visible result; invalid timestamps are stable and last."""
    if sort is None:
        return list(items), 0
    field, direction = sort
    valid: list[tuple[datetime, str, dict[str, Any]]] = []
    invalid: list[dict[str, Any]] = []
    for item in items:
        parsed = _object_sort_time(item.get(field))
        if parsed is None:
            invalid.append(item)
        else:
            valid.append((parsed, str(item.get("id") or ""), item))
    reverse = direction == "desc"
    valid.sort(key=lambda entry: (entry[0], entry[1]), reverse=reverse)
    invalid.sort(key=lambda item: str(item.get("id") or ""), reverse=reverse)
    return [entry[2] for entry in valid] + invalid, len(invalid)


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _object_type_properties(conn, object_type: str) -> list[dict[str, Any]]:
    row = conn.execute(
        "SELECT properties FROM meta_object_type WHERE id=%s",
        (object_type,),
    ).fetchone()
    if not row:
        return []
    props = row["properties"]
    return list(props) if isinstance(props, list) else []


# G18: Auto-redact known e-commerce PII fields that slip through marking config.
# These fields come from raw Niushop source rows and must never be exposed via /v1/objects.
_ECOM_PII_FIELDS = frozenset({
    "mobile", "telephone", "phone",
    "weapp_openid", "wx_openid", "openid",
    "email",
    "pay_password", "password",
    "mobile_country_code",
    "buyer_ip", "last_login_ip", "reg_ip",
    "id_card", "id_card_no",
    "bank_card", "bank_account",
    "real_name",
})

_ECOM_PII_PREFIXES = (
    "mobile", "phone", "tel",
    "openid", "password",
    "email",
)


def _auto_redact_ecom_pii(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip or mask known PII fields from e-commerce object payloads."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    redacted = set(out.get("_redactedFields", []))
    for key in list(out.keys()):
        lk = key.lower()
        is_pii = (
            lk in _ECOM_PII_FIELDS
            or any(lk.startswith(p) for p in _ECOM_PII_PREFIXES)
        )
        if is_pii and lk not in ("telephone",):  # telephone is public business contact
            val = out[key]
            if val is not None and str(val).strip() and str(val) not in ("0", "null", ""):
                out[key] = "[REDACTED]"
                redacted.add(key)
            elif lk in _ECOM_PII_FIELDS:
                out[key] = "[REDACTED]"
                redacted.add(key)
    if redacted:
        out["_redactedFields"] = sorted(redacted)
    return out


class ObjectTypeIn(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    properties: list[dict[str, Any]] = Field(default_factory=list)
    publish: bool = False


class LinkTypeIn(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    srcType: str = Field(min_length=1)
    dstType: str = Field(min_length=1)
    rel: str = Field(min_length=1)
    cardinality: str = "MANY_TO_MANY"
    expectedEdges: int = Field(default=0, ge=0)
    mdoApproved: bool = False
    published: bool = False
    description: str = ""


class LintRequest(BaseModel):
    id: str
    name: str = ""
    published: bool = False
    properties: list[dict[str, Any]] = Field(default_factory=list)


_LINK_SCALE_LIMIT = 1_000_000


def _row_to_link(r: dict[str, Any]) -> dict[str, Any]:
    """Map DB row → API shape. joinMethod/symmetric/rid/status are derived (no new columns)."""
    link_id = r["id"]
    published = bool(r["published"])
    return {
        "id": link_id,
        "name": r["name"],
        "srcType": r["src_type"],
        "dstType": r["dst_type"],
        "rel": r["rel"],
        "cardinality": r["cardinality"],
        "expectedEdges": int(r["expected_edges"]),
        "mdoApproved": bool(r["mdo_approved"]),
        "published": published,
        "description": r["description"] or "",
        # W4-C8a：前端可视化契约字段（缺列时派生默认，失败可降级）
        "joinMethod": r.get("join_method") or "foreign_key",
        "symmetric": bool(r.get("symmetric") or False),
        "constraints": r.get("constraints") or [],
        "rid": f"ri.ontology.main.link-type.{link_id}",
        "status": "Active" if published else "Experimental",
    }


def _check_link_scale(*, expected_edges: int, mdo_approved: bool) -> None:
    if expected_edges > _LINK_SCALE_LIMIT and not mdo_approved:
        raise ApiError(
            code="LINK_SCALE_BLOCKED",
            message="expectedEdges > 1e6 requires mdoApproved (解法 B)",
            status_code=422,
            details={"expectedEdges": expected_edges, "limit": _LINK_SCALE_LIMIT},
        )


@router.get("/v1/ontology/object-types")
def list_object_types(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ontology_compose import filter_object_type_rows

    scope = TenantScope(principal.org_id, principal.project_id)
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT id, name, description, published, properties FROM meta_object_type ORDER BY id"
        ).fetchall()
        rows, installation = filter_object_type_rows(conn, scope, list(rows))
    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "published": r["published"],
            "properties": r["properties"],
        }
        for r in rows
    ]
    log.info("list_object_types count=%s", len(items))
    return {"items": items, "composition": installation}


@router.post("/v1/ontology/object-types")
def create_object_type(
    body: ObjectTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ecom_core_models import CORE_OBJECT_TYPES

    if body.id in CORE_OBJECT_TYPES:
        raise ApiError(
            code="ONTOLOGY_TEMPLATE_WRITE_FORBIDDEN",
            message="installed ecommerce types are customized through an organization overlay",
            status_code=409,
        )
    lint = lint_object_type(
        {
            "id": body.id,
            "published": body.publish,
            "properties": body.properties,
        }
    )
    if body.publish and not lint["ok"]:
        raise ApiError(
            code="BACKING_NOT_UNIQUE",
            message="constitution lint failed; cannot publish",
            status_code=422,
            details=lint,
        )
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_object_type WHERE id=%s", (body.id,)
        ).fetchone()
        if exists:
            raise ApiError(
                code="VALIDATION", message="object type exists", status_code=400
            )
        conn.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties)
            VALUES (%s,%s,%s,%s,%s::jsonb)
            """,
            (
                body.id,
                body.name,
                body.description,
                body.publish,
                json.dumps(body.properties),
            ),
        )
        conn.commit()
    log.info("create_object_type id=%s published=%s", body.id, body.publish)
    return {**body.model_dump(), "lint": lint}


@router.get("/v1/ontology/object-types/{type_id}")
def get_object_type(
    type_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """OT 详情 · W3-C2 补齐派生元数据（RID/PK/TitleKey/Backing 等）。"""
    from aos_api.ontology_compose import filter_object_type_rows

    scope = TenantScope(principal.org_id, principal.project_id)
    with connect(scope) as conn:
        try:
            row = conn.execute(
                """
                SELECT id, name, description, published, properties,
                       required_markings, created_at
                FROM meta_object_type WHERE id=%s
                """,
                (type_id,),
            ).fetchone()
        except Exception:
            row = conn.execute(
                """
                SELECT id, name, description, published, properties
                FROM meta_object_type WHERE id=%s
                """,
                (type_id,),
            ).fetchone()
        rows, _installation = filter_object_type_rows(
            conn, scope, [row] if row is not None else []
        )
    if not rows:
        raise ApiError(
            code="NOT_FOUND", message="object type not found", status_code=404
        )
    row_d = dict(rows[0])
    return build_ot_detail_meta(
        type_id=row_d["id"],
        name=row_d["name"],
        description=row_d.get("description") or "",
        published=bool(row_d.get("published")),
        properties=row_d.get("properties"),
        required_markings=row_d.get("required_markings") or [],
        created_at=row_d.get("created_at"),
    )


class ObjectTypeUpdateIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    properties: list[dict[str, Any]] = Field(default_factory=list)
    publish: bool = False


@router.put("/v1/ontology/object-types/{type_id}")
def update_object_type(
    type_id: str,
    body: ObjectTypeUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """95 · 更新 OT 元数据 / properties（publish 走 constitution lint）。"""
    from aos_api.ecom_core_models import CORE_OBJECT_TYPES

    if type_id in CORE_OBJECT_TYPES:
        raise ApiError(
            code="ONTOLOGY_TEMPLATE_WRITE_FORBIDDEN",
            message="installed ecommerce types are customized through an organization overlay",
            status_code=409,
        )
    lint = lint_object_type(
        {
            "id": type_id,
            "published": body.publish,
            "properties": body.properties,
        }
    )
    if body.publish and not lint["ok"]:
        raise ApiError(
            code="BACKING_NOT_UNIQUE",
            message="constitution lint failed; cannot publish",
            status_code=422,
            details=lint,
        )
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_object_type WHERE id=%s", (type_id,)
        ).fetchone()
        if not exists:
            raise ApiError(
                code="NOT_FOUND", message="object type not found", status_code=404
            )
        conn.execute(
            """
            UPDATE meta_object_type
            SET name=%s, description=%s, published=%s, properties=%s::jsonb
            WHERE id=%s
            """,
            (
                body.name,
                body.description,
                body.publish,
                json.dumps(body.properties),
                type_id,
            ),
        )
        conn.commit()
    log.info(
        "update_object_type id=%s published=%s props=%s",
        type_id,
        body.publish,
        len(body.properties),
    )
    return {
        "id": type_id,
        "name": body.name,
        "description": body.description,
        "properties": body.properties,
        "publish": body.publish,
        "published": body.publish,
        "lint": lint,
    }


@router.get("/v1/ontology/link-types")
def list_link_types(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ontology_compose import filter_link_type_rows

    scope = TenantScope(principal.org_id, principal.project_id)
    with connect(scope) as conn:
        rows = conn.execute(
            """
            SELECT id, name, src_type, dst_type, rel, cardinality,
                   expected_edges, mdo_approved, published, description
            FROM meta_link_type ORDER BY id
            """
        ).fetchall()
        rows, installation = filter_link_type_rows(conn, scope, list(rows))
    items = [_row_to_link(r) for r in rows]
    log.info("list_link_types count=%s", len(items))
    return {"items": items, "composition": installation}


@router.post("/v1/ontology/link-types")
def create_link_type(
    body: LinkTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ecom_core_models import CORE_LINK_TYPES

    if body.id in CORE_LINK_TYPES or body.rel in CORE_LINK_TYPES:
        raise ApiError(
            code="ONTOLOGY_TEMPLATE_WRITE_FORBIDDEN",
            message="installed ecommerce links are customized through an organization overlay",
            status_code=409,
        )
    _check_link_scale(expected_edges=body.expectedEdges, mdo_approved=body.mdoApproved)
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_link_type WHERE id=%s", (body.id,)
        ).fetchone()
        if exists:
            raise ApiError(
                code="VALIDATION", message="link type exists", status_code=400
            )
        conn.execute(
            """
            INSERT INTO meta_link_type (
              id, name, src_type, dst_type, rel, cardinality,
              expected_edges, mdo_approved, published, description
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                body.id,
                body.name,
                body.srcType,
                body.dstType,
                body.rel,
                body.cardinality,
                body.expectedEdges,
                body.mdoApproved,
                body.published,
                body.description,
            ),
        )
        conn.commit()
    log.info("create_link_type id=%s expected=%s", body.id, body.expectedEdges)
    return body.model_dump()


class GraphEdgeIn(BaseModel):
    srcType: str = Field(min_length=1)
    srcId: str = Field(min_length=1)
    rel: str = Field(min_length=1)
    dstType: str = Field(min_length=1)
    dstId: str = Field(min_length=1)


class GraphEdgeBatchIn(BaseModel):
    edges: list[GraphEdgeIn] = Field(default_factory=list)


@router.post("/v1/ontology/edges")
def upsert_graph_edges(
    body: GraphEdgeBatchIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Legacy compatibility writer; disabled in production and for the real tenant."""
    if not allow_dev() or principal.org_id == "org-org":
        raise ApiError(
            code="GRAPH_AUTHORITY_UNAVAILABLE",
            message="compatibility graph_edge writes are disabled for authoritative tenants",
            status_code=409,
        )
    if not body.edges:
        raise ApiError(code="VALIDATION", message="edges required", status_code=400)
    written = 0
    with connect() as conn:
        for e in body.edges:
            result = conn.execute(
                """
                INSERT INTO graph_edge (
                  src_type, src_id, rel, dst_type, dst_id, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (
                  org_id, project_id, src_type, src_id, rel, dst_type, dst_id
                ) DO UPDATE
                  SET org_id=graph_edge.org_id
                WHERE graph_edge.org_id=EXCLUDED.org_id
                  AND graph_edge.project_id=EXCLUDED.project_id
                """,
                (e.srcType, e.srcId, e.rel, e.dstType, e.dstId, *_scope(principal).key),
            )
            if result.rowcount == 0:
                raise ApiError(
                    code="TENANT_KEY_CONFLICT",
                    message="graph edge key belongs to another tenant or legacy scope",
                    status_code=409,
                )
            written += 1
        conn.commit()
    log.info("graph_edges_upsert count=%s", written)
    return {"ok": True, "submitted": written}


@router.get("/v1/ontology/link-types/{link_id}")
def get_link_type(
    link_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ontology_compose import filter_link_type_rows

    scope = _scope(principal)
    with connect(scope) as conn:
        row = conn.execute(
            """
            SELECT id, name, src_type, dst_type, rel, cardinality,
                   expected_edges, mdo_approved, published, description
            FROM meta_link_type WHERE id=%s
            """,
            (link_id,),
        ).fetchone()
        rows, _installation = filter_link_type_rows(
            conn, scope, [row] if row is not None else []
        )
    if not rows:
        raise ApiError(code="NOT_FOUND", message="link type not found", status_code=404)
    return _row_to_link(rows[0])


@router.put("/v1/ontology/link-types/{link_id}")
def update_link_type(
    link_id: str,
    body: LinkTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ecom_core_models import CORE_LINK_TYPES

    if link_id in CORE_LINK_TYPES or body.rel in CORE_LINK_TYPES:
        raise ApiError(
            code="ONTOLOGY_TEMPLATE_WRITE_FORBIDDEN",
            message="installed ecommerce links are customized through an organization overlay",
            status_code=409,
        )
    if body.id != link_id:
        raise ApiError(code="VALIDATION", message="id mismatch", status_code=400)
    _check_link_scale(expected_edges=body.expectedEdges, mdo_approved=body.mdoApproved)
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM meta_link_type WHERE id=%s", (link_id,)
        ).fetchone()
        if not row:
            raise ApiError(
                code="NOT_FOUND", message="link type not found", status_code=404
            )
        conn.execute(
            """
            UPDATE meta_link_type SET
              name=%s, src_type=%s, dst_type=%s, rel=%s, cardinality=%s,
              expected_edges=%s, mdo_approved=%s, published=%s, description=%s
            WHERE id=%s
            """,
            (
                body.name,
                body.srcType,
                body.dstType,
                body.rel,
                body.cardinality,
                body.expectedEdges,
                body.mdoApproved,
                body.published,
                body.description,
                link_id,
            ),
        )
        conn.commit()
    return body.model_dump()


@router.delete("/v1/ontology/link-types/{link_id}")
def delete_link_type(
    link_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Delete metadata only — does not cascade graph_edge."""
    from aos_api.ecom_core_models import CORE_LINK_TYPES

    if link_id in CORE_LINK_TYPES:
        raise ApiError(
            code="ONTOLOGY_TEMPLATE_WRITE_FORBIDDEN",
            message="installed ecommerce links cannot be deleted from the platform template",
            status_code=409,
        )
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM meta_link_type WHERE id=%s", (link_id,)
        ).fetchone()
        if not row:
            raise ApiError(
                code="NOT_FOUND", message="link type not found", status_code=404
            )
        conn.execute("DELETE FROM meta_link_type WHERE id=%s", (link_id,))
        conn.commit()
    log.info("delete_link_type id=%s", link_id)
    return {"ok": True, "id": link_id}


@router.get("/v1/objects/{object_type}")
def list_objects(
    object_type: str,
    principal: Principal = Depends(require_principal),
    branch: str | None = None,
    sort_by: str | None = Query(default=None, alias="sortBy"),
    sort_direction: str | None = Query(default=None, alias="sortDirection"),
) -> dict[str, Any]:
    """List instances. ``branch`` selects effective view (89 v2 overlay)."""
    from aos_api.ontology_compose import assert_object_type_visible

    scope = _scope(principal)
    with connect(scope) as conn:
        assert_object_type_visible(conn, scope, object_type)
        object_sort = _resolve_object_sort(object_type, sort_by, sort_direction)
        from aos_api.branch_store import effective_objects
        prop_defs = _object_type_properties(conn, object_type)
        rows = effective_objects(conn, _scope(principal), object_type, branch)
        items = []
        for r in rows:
            if not can_access_object(principal, conn, object_type, r["object_id"]):
                continue
            raw = {"id": r["object_id"], "type": object_type, **(r["props"] or {})}
            redacted = apply_field_redaction(principal, raw, prop_defs, conn=conn)
            # G18: auto-redact known e-commerce PII fields not caught by marking config
            redacted = _auto_redact_ecom_pii(redacted)
            redacted.update(
                build_object_display_projection(object_type, r["object_id"], redacted)
            )
            items.append(redacted)
    items, invalid_sort_value_count = _sort_object_items(items, object_sort)
    out: dict[str, Any] = {"items": items, "total": len(items)}
    if object_sort:
        out["sort"] = {
            "by": object_sort[0],
            "direction": object_sort[1],
            "nulls": "last",
            "tieBreak": "objectId",
            "invalidValueCount": invalid_sort_value_count,
        }
        if invalid_sort_value_count:
            log.warning(
                "object_sort_invalid_values type=%s field=%s count=%s",
                object_type,
                object_sort[0],
                invalid_sort_value_count,
            )
    if branch:
        out["branch"] = branch
    return out


@router.get("/v1/objects/{object_type}/{object_id}")
def get_object(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
    branch: str | None = None,
) -> dict[str, Any]:
    from aos_api.ontology_compose import assert_object_type_visible

    scope = _scope(principal)
    with connect(scope) as conn:
        assert_object_type_visible(conn, scope, object_type)
        from aos_api.branch_store import effective_object
        ensure_object_access(principal, conn, object_type, object_id)
        prop_defs = _object_type_properties(conn, object_type)
        hit = effective_object(conn, _scope(principal), object_type, object_id, branch)
        if not hit:
            raise ApiError(
                code="NOT_FOUND", message="object not found", status_code=404
            )
        raw = {"id": object_id, "type": object_type, **(hit["props"] or {})}
        out = apply_field_redaction(principal, raw, prop_defs, conn=conn)
        out = _auto_redact_ecom_pii(out)
        out.update(build_object_display_projection(object_type, object_id, out))
    if branch:
        out = {**out, "branch": branch}
    return out


class ObjectPutIn(BaseModel):
    props: dict[str, Any] = Field(default_factory=dict)
    op: str = "upsert"


@router.put("/v1/objects/{object_type}/{object_id}")
def put_object(
    object_type: str,
    object_id: str,
    body: ObjectPutIn,
    principal: Principal = Depends(require_principal),
    branch: str | None = None,
) -> dict[str, Any]:
    """89 v2 · write branch overlay only. Production writes stay on Draft path."""
    from aos_api.ecom_core_models import CORE_OBJECT_TYPES

    if object_type in CORE_OBJECT_TYPES:
        raise ApiError(
            code="ONTOLOGY_LEGACY_BRANCH_WRITE_FORBIDDEN",
            message="ecommerce objects use the authoritative store and Installation Overlay path",
            status_code=409,
        )
    if not branch:
        raise ApiError(
            code="VALIDATION",
            message="PUT requires ?branch= for overlay writes; production uses Draft",
            status_code=400,
        )
    with connect() as conn:
        from aos_api.branch_store import upsert_overlay
        ot = conn.execute(
            "SELECT 1 FROM meta_object_type WHERE id=%s", (object_type,)
        ).fetchone()
        if not ot:
            raise ApiError(
                code="NOT_FOUND", message="object type not found", status_code=404
            )
        upsert_overlay(
            conn,
            _scope(principal),
            branch,
            object_type,
            object_id,
            body.props or {},
            op=body.op or "upsert",
        )
        conn.commit()
    log.info(
        "object_overlay_put type=%s id=%s branch=%s op=%s",
        object_type,
        object_id,
        branch,
        body.op,
    )
    return {
        "ok": True,
        "objectType": object_type,
        "objectId": object_id,
        "branch": branch,
        "op": body.op,
    }


@router.get("/v1/objects/{object_type}/{object_id}/neighbors")
def neighbors(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """1-hop compatibility projection from the authoritative GraphSnapshot."""
    try:
        snapshot = get_authoritative_graph_service().query(
            _scope(principal),
            GraphQueryDTO(
                seeds=[{"objectType": object_type, "objectId": object_id}],
                hops=1,
                maxNodes=500,
                direction="both",
            ),
        )
    except ApiError as exc:
        if not (exc.code == "GRAPH_AUTHORITY_UNAVAILABLE" and allow_dev() and principal.org_id == "dev-org"):
            raise
        with connect(_scope(principal)) as conn:
            rows = conn.execute(
                "SELECT rel,dst_type,dst_id FROM graph_edge WHERE src_type=%s AND src_id=%s "
                "AND org_id=%s AND project_id=%s",
                (object_type, object_id, *_scope(principal).key),
            ).fetchall()
        return {
            "items": [{"rel": row["rel"], "type": row["dst_type"], "id": row["dst_id"]} for row in rows],
            "engine": "adjacency_table",
            "sourceAuthority": "compat_projection",
        }
    seed_key = f"{object_type}:{object_id}"
    nodes = {node.key: node for node in snapshot.nodes}
    items: list[dict[str, Any]] = []
    for edge in snapshot.edges:
        if edge.source == seed_key and edge.target in nodes:
            target = nodes[edge.target]
            items.append({
                "rel": edge.relationType, "type": target.objectType, "id": target.objectId,
                "direction": "outgoing", "edgeAuthority": edge.edgeAuthority,
            })
        elif edge.target == seed_key and edge.source in nodes:
            source = nodes[edge.source]
            items.append({
                "rel": edge.relationType, "type": source.objectType, "id": source.objectId,
                "direction": "incoming", "edgeAuthority": edge.edgeAuthority,
            })
    return {
        "items": items,
        "engine": "ecom_authoritative",
        "sourceAuthority": snapshot.sourceAuthority,
        "watermark": snapshot.snapshot.watermark,
        "schemaEtag": snapshot.schemaEtag,
    }


@router.get("/v1/wiki/{object_type}/{object_id}/versions")
def list_wiki_versions(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """93 · 只读历史版本（审批写回前快照）· TWA.8 按区。"""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, body, draft_id, created_at
            FROM wiki_page_version
            WHERE object_type=%s AND object_id=%s
              AND org_id=%s AND project_id=%s
            ORDER BY id DESC
            LIMIT 50
            """,
            (object_type, object_id, principal.org_id, principal.project_id),
        ).fetchall()
    items = []
    for r in rows:
        body = r["body"] or {}
        summary = body.get("summary") if isinstance(body, dict) else None
        created = r["created_at"]
        items.append(
            {
                "id": int(r["id"]),
                "createdAt": created.isoformat()
                if hasattr(created, "isoformat")
                else str(created),
                "summary": summary,
                "draftId": r["draft_id"],
            }
        )
    return {"objectType": object_type, "objectId": object_id, "items": items}


@router.get("/v1/wiki/{object_type}/{object_id}/versions/{version_id}")
def get_wiki_version(
    object_type: str,
    object_id: str,
    version_id: int,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, body, draft_id, created_at
            FROM wiki_page_version
            WHERE object_type=%s AND object_id=%s AND id=%s
              AND org_id=%s AND project_id=%s
            """,
            (
                object_type,
                object_id,
                version_id,
                principal.org_id,
                principal.project_id,
            ),
        ).fetchone()
    if not row:
        raise ApiError(
            code="NOT_FOUND", message="wiki version not found", status_code=404
        )
    created = row["created_at"]
    return {
        "id": int(row["id"]),
        "objectType": object_type,
        "objectId": object_id,
        "body": row["body"],
        "draftId": row["draft_id"],
        "createdAt": created.isoformat()
        if hasattr(created, "isoformat")
        else str(created),
    }


@router.get("/v1/wiki/{object_type}/coverage-index")
def wiki_coverage_index(
    object_type: str,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """O1-UX5 · tenant-authoritative Object×Wiki coverage without expected 404 fan-out."""
    scope = _scope(principal)
    operational_clause = ""
    if object_type == "Order":
        operational_clause = " AND oi.props->>'status'='active' AND COALESCE(oi.props->>'isDelete','0')='0'"
    elif object_type == "Product":
        operational_clause = " AND oi.props->>'status'='active' AND COALESCE(oi.props->>'isDelete','0')='0' AND oi.props->>'state'='1'"
    with connect(scope) as conn:
        rows = conn.execute(
            f"""
            SELECT oi.object_id,oi.props,wp.body,
                   (SELECT COUNT(*) FROM wiki_page_version wv
                     WHERE wv.org_id=oi.org_id AND wv.project_id=oi.project_id
                       AND wv.object_type=oi.object_type AND wv.object_id=oi.object_id) AS version_count,
                   (SELECT MAX(wv.created_at) FROM wiki_page_version wv
                     WHERE wv.org_id=oi.org_id AND wv.project_id=oi.project_id
                       AND wv.object_type=oi.object_type AND wv.object_id=oi.object_id) AS last_updated_at
              FROM obj_instance oi
              LEFT JOIN wiki_page wp
                ON wp.org_id=oi.org_id AND wp.project_id=oi.project_id
               AND wp.object_type=oi.object_type AND wp.object_id=oi.object_id
             WHERE oi.org_id=%s AND oi.project_id=%s AND oi.object_type=%s{operational_clause}
             ORDER BY oi.object_id
             LIMIT %s
            """,
            (*scope.key, object_type, limit),
        ).fetchall()
        total_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM obj_instance oi WHERE oi.org_id=%s AND oi.project_id=%s AND oi.object_type=%s{operational_clause}",
            (*scope.key, object_type),
        ).fetchone()
        items = []
        for row in rows:
            object_id = str(row["object_id"])
            if not can_access_object(principal, conn, object_type, object_id):
                continue
            body = row["body"] if isinstance(row["body"], dict) else {}
            display = build_object_display_projection(object_type, object_id, row["props"] or {})
            items.append({
                "objectType": object_type,
                "objectId": object_id,
                "covered": row["body"] is not None,
                "summary": str(body.get("summary") or ""),
                "versionCount": int(row["version_count"] or 0),
                "displayLabel": display["_displayLabel"],
                "sourceRecordLabel": display["_sourceRecordLabel"],
                "lastUpdatedAt": row["last_updated_at"].isoformat() if row["last_updated_at"] else None,
            })
    covered = sum(1 for item in items if item["covered"])
    return {
        "objectType": object_type,
        "items": items,
        "coverage": {"covered": covered, "gaps": len(items) - covered, "visible": len(items), "total": int(total_row["count"] or 0)},
    }


@router.get("/v1/wiki/{object_type}/{object_id}")
def get_wiki(
    object_type: str,
    object_id: str,
    allow_missing: bool = Query(default=False, alias="allowMissing"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.tenant_prefix import wiki_space_id

    with connect() as conn:
        row = conn.execute(
            """
            SELECT body FROM wiki_page
            WHERE object_type=%s AND object_id=%s
              AND org_id=%s AND project_id=%s
            """,
            (object_type, object_id, principal.org_id, principal.project_id),
        ).fetchone()
    if not row:
        if allow_missing:
            return {
                "objectType": object_type,
                "objectId": object_id,
                "body": {},
                "exists": False,
                "orgId": principal.org_id,
                "projectId": principal.project_id,
                "spaceId": wiki_space_id(principal.org_id, principal.project_id),
            }
        raise ApiError(code="NOT_FOUND", message="wiki not found", status_code=404)
    return {
        "objectType": object_type,
        "objectId": object_id,
        "body": row["body"],
        "exists": True,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
        "spaceId": wiki_space_id(principal.org_id, principal.project_id),
    }


@router.get("/v1/funnel/{object_type}/status")
def funnel_status(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT stage, detail FROM funnel_status WHERE object_type=%s "
            "AND org_id=%s AND project_id=%s",
            (object_type, *_scope(principal).key),
        ).fetchone()
    if not row:
        raise ApiError(
            code="NOT_FOUND", message="funnel status missing", status_code=404
        )
    return {
        "objectType": object_type,
        "stage": row["stage"],
        "detail": row["detail"],
    }


@router.post("/v1/ontology/constitution/lint")
def constitution_lint(
    body: LintRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    return lint_object_type(body.model_dump())


_GRAPH_HEALTH_SCORE_VERSION = "GH-SCORE-v2"
_REQUIRED_LINK_TYPES_BY_OBJECT: dict[str, frozenset[str]] = {
    "Shop": frozenset({"Shop.hasWeapp"}),
    "Weapp": frozenset({"Shop.hasWeapp"}),
    "Product": frozenset({"Product.inCategory"}),
    "ProductSku": frozenset({"ProductSku.ofProduct"}),
    "ProductReview": frozenset({"Product.hasReview"}),
    "Order": frozenset({"Order.fromWeapp"}),
    "OrderLine": frozenset({"Order.lines"}),
    "Payment": frozenset({"Order.hasPayment"}),
    "Shipment": frozenset({"Order.fulfilledBy"}),
}


def _graph_health_score_breakdown(
    *,
    dangling_affected: int,
    dangling_denominator: int,
    conflict_affected: int,
    conflict_denominator: int,
    orphan_affected: int,
    orphan_denominator: int,
    rule_affected: int,
    rule_denominator: int,
) -> tuple[int, list[dict[str, Any]]]:
    specs = [
        ("GH-01", dangling_affected, dangling_denominator, 0.01, 40),
        ("GH-02", conflict_affected, conflict_denominator, 0.10, 25),
        ("GH-03", orphan_affected, orphan_denominator, 0.10, 25),
        ("GH-04", rule_affected, rule_denominator, 0.05, 10),
    ]
    deductions = 0.0
    breakdown: list[dict[str, Any]] = []
    for code, affected, denominator, threshold, weight in specs:
        rate = affected / denominator if denominator else 0.0
        deduction = weight * min(1.0, rate / threshold) if denominator else 0.0
        deductions += deduction
        breakdown.append(
            {
                "code": code,
                "affectedObjects": affected,
                "denominator": denominator,
                "rate": round(rate, 6),
                "threshold": threshold,
                "maxDeduction": weight,
                "deduction": round(deduction, 2),
            }
        )
    return max(0, min(100, round(100 - deductions))), breakdown


def _classify_graph_properties(row: Any) -> dict[str, list[str]]:
    from aos_api.ecom_core_models import DERIVED_PROPERTIES, OPTIONAL_PROPERTIES, REQUIRED_PROPERTIES

    object_type = str(row["object_type"])
    declared = row["properties"] if isinstance(row["properties"], list) else []
    canonical = {
        str(prop.get("name"))
        for prop in declared
        if isinstance(prop, dict) and prop.get("name")
    }
    canonical |= set(REQUIRED_PROPERTIES.get(object_type, frozenset()))
    canonical |= set(OPTIONAL_PROPERTIES.get(object_type, frozenset()))
    canonical |= set(DERIVED_PROPERTIES.get(object_type, frozenset()))
    result: dict[str, list[str]] = {
        "canonical": [], "system": [], "compatibilityAlias": [], "actualConflict": [],
    }
    props = row["props"] if isinstance(row["props"], dict) else {}
    for key in props:
        if key in canonical:
            result["canonical"].append(key)
        elif key.startswith("_") or key.endswith("SourceTimezone") or key == "currencyScale":
            result["system"].append(key)
        elif "_" in key:
            result["compatibilityAlias"].append(key)
        else:
            result["actualConflict"].append(key)
    return result


@router.get("/v1/ontology/graph-health")
def graph_health(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    """T2.10 + 94 · GH metrics + issues（真悬空边 / 属性键冲突）。"""
    scope = _scope(principal)
    with connect(scope) as conn:
        types = conn.execute("SELECT COUNT(*) AS c FROM meta_object_type").fetchone()
        authority_objs = conn.execute(
            "SELECT COUNT(*) AS c FROM ecom_object WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL",
            scope.key,
        ).fetchone()
        authoritative = int(authority_objs["c"]) > 0
        if authoritative:
            authority_meta = get_authoritative_graph_service().metadata(scope)
            objs = {"c": authority_meta["objects"]}
            edges = {"c": authority_meta["edges"]}
            orphans = conn.execute(
                """
                SELECT COUNT(*) AS c FROM ecom_object o
                WHERE o.org_id=%s AND o.workspace_id=%s AND o.deleted_at IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM ecom_link e
                    WHERE e.org_id=o.org_id AND e.workspace_id=o.workspace_id AND e.deleted_at IS NULL
                      AND ((e.source_platform=o.platform
                            AND e.source_shop_or_marketplace_id=o.shop_or_marketplace_id
                            AND e.source_object_type=o.object_type AND e.source_external_id=o.external_id)
                        OR (e.target_platform=o.platform
                            AND e.target_shop_or_marketplace_id=o.shop_or_marketplace_id
                            AND e.target_object_type=o.object_type AND e.target_external_id=o.external_id))
                  )
                """,
                scope.key,
            ).fetchone()
            dangling = conn.execute(
                """
                SELECT COUNT(*) AS c FROM ecom_link e
                WHERE e.org_id=%s AND e.workspace_id=%s AND e.deleted_at IS NULL
                  AND (NOT EXISTS (
                    SELECT 1 FROM ecom_object s WHERE s.org_id=e.org_id AND s.workspace_id=e.workspace_id
                      AND s.platform=e.source_platform AND s.shop_or_marketplace_id=e.source_shop_or_marketplace_id
                      AND s.object_type=e.source_object_type AND s.external_id=e.source_external_id
                      AND s.deleted_at IS NULL
                  ) OR NOT EXISTS (
                    SELECT 1 FROM ecom_object d WHERE d.org_id=e.org_id AND d.workspace_id=e.workspace_id
                      AND d.platform=e.target_platform AND d.shop_or_marketplace_id=e.target_shop_or_marketplace_id
                      AND d.object_type=e.target_object_type AND d.external_id=e.target_external_id
                      AND d.deleted_at IS NULL
                  ))
                """,
                scope.key,
            ).fetchone()
            prop_rows = conn.execute(
                """
                SELECT o.object_type,o.external_id AS object_id,o.properties AS props,t.properties
                FROM ecom_object o JOIN meta_object_type t ON t.id=o.object_type
                WHERE o.org_id=%s AND o.workspace_id=%s AND o.deleted_at IS NULL
                ORDER BY o.object_type,o.external_id LIMIT 2000
                """,
                scope.key,
            ).fetchall()
            identity_rows = conn.execute(
                """
                SELECT object_type,platform,shop_or_marketplace_id,external_id
                FROM ecom_object
                WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL
                """,
                scope.key,
            ).fetchall()
            required_link_rows = conn.execute(
                """
                SELECT link_type,
                       source_platform,source_shop_or_marketplace_id,source_object_type,source_external_id,
                       target_platform,target_shop_or_marketplace_id,target_object_type,target_external_id
                FROM ecom_link
                WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL
                """,
                scope.key,
            ).fetchall()
        else:
            objs = conn.execute(
                "SELECT COUNT(*) AS c FROM obj_instance WHERE org_id=%s AND project_id=%s", scope.key
            ).fetchone()
            edges = conn.execute(
                "SELECT COUNT(*) AS c FROM graph_edge WHERE org_id=%s AND project_id=%s", scope.key
            ).fetchone()
            orphans = conn.execute(
                """
                SELECT COUNT(*) AS c FROM obj_instance o WHERE o.org_id=%s AND o.project_id=%s
                  AND NOT EXISTS (SELECT 1 FROM graph_edge e WHERE e.org_id=%s AND e.project_id=%s
                    AND ((e.src_type=o.object_type AND e.src_id=o.object_id)
                      OR (e.dst_type=o.object_type AND e.dst_id=o.object_id)))
                """,
                (*scope.key, *scope.key),
            ).fetchone()
            dangling = conn.execute(
                """
                SELECT COUNT(*) AS c FROM graph_edge e WHERE e.org_id=%s AND e.project_id=%s
                  AND (NOT EXISTS (SELECT 1 FROM obj_instance s WHERE s.object_type=e.src_type
                    AND s.object_id=e.src_id AND s.org_id=%s AND s.project_id=%s)
                  OR NOT EXISTS (SELECT 1 FROM obj_instance d WHERE d.object_type=e.dst_type
                    AND d.object_id=e.dst_id AND d.org_id=%s AND d.project_id=%s))
                """,
                (*scope.key, *scope.key, *scope.key),
            ).fetchone()
            prop_rows = conn.execute(
                """
                SELECT o.object_type,o.object_id,o.props,t.properties FROM obj_instance o
                JOIN meta_object_type t ON t.id=o.object_type
                WHERE o.org_id=%s AND o.project_id=%s ORDER BY o.object_type,o.object_id LIMIT 2000
                """,
                scope.key,
            ).fetchall()
            identity_rows = []
            required_link_rows = []
    dangling_n = int(dangling["c"])
    raw_unlinked_n = int(orphans["c"])
    conflict_objects: set[tuple[str, str]] = set()
    conflict_samples: list[str] = []
    property_classification = {
        "canonical": 0,
        "system": 0,
        "compatibilityAlias": 0,
        "actualConflict": 0,
    }
    for row in prop_rows:
        classified = _classify_graph_properties(row) if authoritative else {
            "canonical": [], "system": [], "compatibilityAlias": [], "actualConflict": [],
        }
        for category in property_classification:
            property_classification[category] += len(classified[category])
        if classified["actualConflict"]:
            conflict_objects.add((str(row["object_type"]), str(row["object_id"])))
            if len(conflict_samples) < 5:
                conflict_samples.append(
                    f"{row['object_type']}/{row['object_id']}:{','.join(classified['actualConflict'][:3])}"
                )
    conflict_n = len(conflict_objects)

    required_link_eligible: set[tuple[str, str, str, str]] = set()
    required_link_covered: set[tuple[str, str, str, str]] = set()
    if authoritative:
        for row in identity_rows:
            object_type = str(row["object_type"])
            if object_type in _REQUIRED_LINK_TYPES_BY_OBJECT:
                required_link_eligible.add(
                    (object_type, str(row["platform"]), str(row["shop_or_marketplace_id"]), str(row["external_id"]))
                )
        for row in required_link_rows:
            link_type = str(row["link_type"])
            source_type = str(row["source_object_type"])
            target_type = str(row["target_object_type"])
            if link_type in _REQUIRED_LINK_TYPES_BY_OBJECT.get(source_type, frozenset()):
                required_link_covered.add(
                    (source_type, str(row["source_platform"]), str(row["source_shop_or_marketplace_id"]), str(row["source_external_id"]))
                )
            if link_type in _REQUIRED_LINK_TYPES_BY_OBJECT.get(target_type, frozenset()):
                required_link_covered.add(
                    (target_type, str(row["target_platform"]), str(row["target_shop_or_marketplace_id"]), str(row["target_external_id"]))
                )
    required_orphans = required_link_eligible - required_link_covered
    orphan_n = len(required_orphans) if authoritative else raw_unlinked_n
    from aos_api import ttl_job

    ttl_snap = ttl_job.status_snapshot(_scope(principal))
    metrics = {
        "objectTypes": int(types["c"]),
        "instances": int(objs["c"]),
        "edges": int(edges["c"]),
        "orphanInstances": orphan_n,
        "unlinkedInstances": raw_unlinked_n,
        "danglingEdges": dangling_n,
        "propConflicts": conflict_n,
        "propertyClassification": property_classification,
        "requiredLinkEligible": len(required_link_eligible),
        "archiveCandidates": int(ttl_snap["archiveCandidates"]),
        "engine": "ecom_authoritative" if authoritative else "adjacency_table",
        "ageAvailable": False,
        "insightTtlDays": ttl_snap["ttlDays"],
    }
    if authoritative:
        metrics["graphWatermark"] = authority_meta["watermark"]
        metrics["schemaEtag"] = authority_meta["schemaEtag"]
    issues: list[dict[str, Any]] = []
    if dangling_n > 0:
        issues.append(
            {
                "code": "GH-01",
                "severity": "bad",
                "object": f"悬空边 ×{dangling_n}",
                "message": (
                    "ecom_link 端点在活跃 ecom_object 中不存在"
                    if authoritative else "graph_edge 端点在 obj_instance 中不存在"
                ),
                "href": "/workshop/graph",
            }
        )
    elif metrics["edges"] == 0:
        issues.append(
            {
                "code": "GH-01",
                "severity": "warn",
                "object": "图谱边",
                "message": f"edges=0 · engine={metrics['engine']}",
                "href": "/workshop/graph",
            }
        )
    if conflict_n > 0:
        issues.append(
            {
                "code": "GH-02",
                "severity": "warn",
                "object": f"属性冲突 ×{conflict_n}",
                "message": "实例 props 含未声明键 · " + "; ".join(conflict_samples[:3]),
                "href": "/ontology",
                "samples": [
                    {"objectType": object_type, "objectId": object_id}
                    for object_type, object_id in sorted(conflict_objects)[:20]
                ],
            }
        )
    if orphan_n > 0:
        issues.append(
            {
                "code": "GH-03",
                "severity": "warn",
                "object": f"必需关系缺失 ×{orphan_n}",
                "message": (
                    "只统计声明了必需 Link 约束但未命中的对象；允许独立对象不计错"
                    if authoritative else "兼容图未加载必需 Link 注册表"
                ),
                "href": "/workshop/graph",
                "samples": [
                    {
                        "objectType": object_type,
                        "objectId": external_id,
                    }
                    for object_type, platform, shop_id, external_id in sorted(required_orphans)[:20]
                ],
            }
        )
    if authoritative:
        score, breakdown = _graph_health_score_breakdown(
            dangling_affected=dangling_n,
            dangling_denominator=int(metrics["edges"]),
            conflict_affected=conflict_n,
            conflict_denominator=int(metrics["instances"]),
            orphan_affected=orphan_n,
            orphan_denominator=len(required_link_eligible),
            rule_affected=0,
            rule_denominator=int(metrics["instances"]),
        )
        score_status = "known"
    else:
        score = None
        breakdown = []
        score_status = "unknown"
    log.info(
        "graph_health score=%s edges=%s dangling=%s conflicts=%s issues=%s",
        score,
        metrics["edges"],
        dangling_n,
        conflict_n,
        len(issues),
    )
    return {
        "score": score,
        "scoreStatus": score_status,
        "scoreVersion": _GRAPH_HEALTH_SCORE_VERSION,
        "breakdown": breakdown,
        "metrics": metrics,
        "issues": issues,
        "archivePreview": ttl_snap.get("preview") or [],
    }


class BranchIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    baseRef: str = "main"


@router.get("/v1/ontology/branches")
def list_branches(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    scope = _scope(principal)
    with connect(scope) as conn:
        from aos_api.branch_store import change_count
        rows = conn.execute(
            "SELECT id, name, base_ref, readonly FROM meta_branch "
            "WHERE org_id=%s AND project_id=%s ORDER BY id",
            scope.key,
        ).fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "baseRef": r["base_ref"],
                    "readonly": r["readonly"],
                    "changeCount": change_count(conn, scope, r["id"]),
                }
            )
    return {"items": items}


@router.post("/v1/ontology/branches")
def create_branch(
    body: BranchIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """89 · 新建开发分支；v2 起可挂 overlay 写/diff/merge。"""
    _ = principal
    bid = body.id.strip()
    if not bid or not bid.replace("-", "").replace("_", "").isalnum():
        raise ApiError(
            code="VALIDATION", message="id must be alphanumeric/_/-", status_code=400
        )
    scope = _scope(principal)
    with connect(scope) as conn:
        base = body.baseRef.strip() or "main"
        if base not in {"main", "master"}:
            base_row = conn.execute(
                "SELECT 1 FROM meta_branch WHERE id=%s AND org_id=%s AND project_id=%s",
                (base, *_scope(principal).key),
            ).fetchone()
            if not base_row:
                raise ApiError(
                    code="VALIDATION",
                    message=f"baseRef not found: {base}",
                    status_code=400,
                )
        result = conn.execute(
            """
            INSERT INTO meta_branch (
              id, name, base_ref, readonly, org_id, project_id
            ) VALUES (%s,%s,%s,FALSE,%s,%s)
            ON CONFLICT (org_id, project_id, id) DO NOTHING
            RETURNING id
            """,
            (bid, body.name.strip(), base, *_scope(principal).key),
        )
        if result.fetchone() is None:
            raise ApiError(
                code="TENANT_KEY_CONFLICT",
                message=f"branch key already exists in a tenant or legacy scope: {bid}",
                status_code=409,
            )
        conn.commit()
    log.info("branch_created id=%s base=%s", bid, body.baseRef)
    return {
        "id": bid,
        "name": body.name.strip(),
        "baseRef": base,
        "readonly": False,
        "changeCount": 0,
    }


class CheckoutIn(BaseModel):
    objectType: str = Field(min_length=1)
    objectId: str = Field(min_length=1)
    patch: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/ontology/branches/{branch_id}/diff")
def branch_diff(
    branch_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = _scope(principal)
    with connect(scope) as conn:
        from aos_api.branch_store import diff_branch

        return diff_branch(conn, scope, branch_id)


@router.post("/v1/ontology/branches/{branch_id}/merge")
def branch_merge(
    branch_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = _scope(principal)
    with connect(scope) as conn:
        from aos_api.branch_store import merge_branch

        out = merge_branch(conn, scope, branch_id)
        conn.commit()
    log.info("branch_merged id=%s merged=%s", branch_id, out.get("merged"))
    return out


@router.post("/v1/ontology/branches/{branch_id}/checkout")
def branch_checkout(
    branch_id: str,
    body: CheckoutIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Copy base object into branch overlay (optional patch) for demo/edit."""
    scope = _scope(principal)
    with connect(scope) as conn:
        from aos_api.branch_store import checkout_object

        out = checkout_object(
            conn,
            scope,
            branch_id,
            body.objectType,
            body.objectId,
            body.patch or None,
        )
        conn.commit()
    log.info(
        "branch_checkout branch=%s type=%s id=%s",
        branch_id,
        body.objectType,
        body.objectId,
    )
    return {"ok": True, "branchId": branch_id, **out}


def _okf_col(src: str, ot: str, dst: str, ok: bool = True) -> dict[str, Any]:
    """Shortcut for an OKF column entry."""
    return {"src": src, "dst": f"{ot}.{dst}", "ok": ok}


# ---------------------------------------------------------------------------
# OKF defaults for all 12 ecommerce OTs.
#
# Source column names are derived from ec_normalizer.py's 12 mapper functions
# (the authoritative source→ontology field mappings). Every REQUIRED_PROPERTIES
# field for each OT is covered with ok=True. Optional source columns that the
# normalizer also emits are included with ok=True where they enrich the mapping.
#
# This replaces the old single-OT Order-only default and the removed env/bio
# examples. Industries other than "ecom" are not supported by the multi-type
# endpoint anyway (see get_okf_mapping_types guard).
# ---------------------------------------------------------------------------
_OKF_DEFAULTS: dict[str, dict[str, Any]] = {
    "ecom_Shop": {
        "industry": "ecom",
        "objectType": "Shop",
        "label": "微商城电商 · Shop",
        "columns": [
            _okf_col("site_id", "Shop", "id"),
            _okf_col("site_name", "Shop", "name"),
            _okf_col("(constant)", "Shop", "status"),
            _okf_col("(constant=CNY)", "Shop", "currency"),
            _okf_col("(constant=+08:00)", "Shop", "timezone"),
        ],
    },
    "ecom_Product": {
        "industry": "ecom",
        "objectType": "Product",
        "label": "微商城电商 · Product",
        "columns": [
            _okf_col("goods_id", "Product", "id"),
            _okf_col("site_id", "Product", "shopId"),
            _okf_col("goods_name", "Product", "title"),
            _okf_col("(constant=active)", "Product", "status"),
            _okf_col("category_id", "Product", "categoryId"),
            _okf_col("create_time", "Product", "createdAt"),
            _okf_col("modify_time", "Product", "updatedAt"),
        ],
    },
    "ecom_ProductSku": {
        "industry": "ecom",
        "objectType": "ProductSku",
        "label": "微商城电商 · ProductSku",
        "columns": [
            _okf_col("sku_id", "ProductSku", "id"),
            _okf_col("goods_id", "ProductSku", "productId"),
            _okf_col("(constant=active)", "ProductSku", "status"),
            _okf_col("sku_no", "ProductSku", "barcode"),
            _okf_col("price", "ProductSku", "price"),
            _okf_col("(constant=CNY)", "ProductSku", "currency"),
            _okf_col("modify_time", "ProductSku", "updatedAt"),
        ],
    },
    "ecom_Category": {
        "industry": "ecom",
        "objectType": "Category",
        "label": "微商城电商 · Category",
        "columns": [
            _okf_col("category_id", "Category", "id"),
            _okf_col("pid", "Category", "parentCategoryId"),
            _okf_col("category_name", "Category", "name"),
            _okf_col("(constant=active)", "Category", "status"),
            _okf_col("(now)", "Category", "updatedAt"),
        ],
    },
    "ecom_Order": {
        "industry": "ecom",
        "objectType": "Order",
        "label": "微商城电商 · Order",
        "columns": [
            _okf_col("order_id", "Order", "id"),
            _okf_col("site_id", "Order", "shopId"),
            _okf_col("order_status", "Order", "status"),
            _okf_col("order_money", "Order", "totalAmount"),
            _okf_col("(constant=CNY)", "Order", "currency"),
            _okf_col("create_time", "Order", "createdAt"),
            _okf_col("modify_time", "Order", "updatedAt"),
        ],
    },
    "ecom_OrderLine": {
        "industry": "ecom",
        "objectType": "OrderLine",
        "label": "微商城电商 · OrderLine",
        "columns": [
            _okf_col("order_goods_id", "OrderLine", "id"),
            _okf_col("order_id", "OrderLine", "orderId"),
            _okf_col("sku_id", "OrderLine", "skuId"),
            _okf_col("num", "OrderLine", "quantity"),
            _okf_col("price", "OrderLine", "unitPrice"),
            _okf_col("real_goods_money", "OrderLine", "lineAmount"),
            _okf_col("(constant=CNY)", "OrderLine", "currency"),
            _okf_col("create_time", "OrderLine", "updatedAt"),
        ],
    },
    "ecom_Shipment": {
        "industry": "ecom",
        "objectType": "Shipment",
        "label": "微商城电商 · Shipment",
        "columns": [
            _okf_col("id", "Shipment", "id"),
            _okf_col("order_id", "Shipment", "orderId"),
            _okf_col("(constant=active)", "Shipment", "status"),
            _okf_col("express_company_id", "Shipment", "carrier"),
            _okf_col("delivery_no", "Shipment", "trackingNo"),
            _okf_col("delivery_time", "Shipment", "shippedAt"),
            _okf_col("delivery_time", "Shipment", "updatedAt"),
        ],
    },
    "ecom_CustomerLite": {
        "industry": "ecom",
        "objectType": "CustomerLite",
        "label": "微商城电商 · CustomerLite",
        "columns": [
            _okf_col("member_id", "CustomerLite", "id"),
            _okf_col("member_level", "CustomerLite", "memberLevel"),
            _okf_col("(constant=active)", "CustomerLite", "status"),
            _okf_col("reg_time", "CustomerLite", "createdAt"),
            _okf_col("last_visit_time", "CustomerLite", "updatedAt"),
        ],
    },
    "ecom_Weapp": {
        "industry": "ecom",
        "objectType": "Weapp",
        "label": "微商城电商 · Weapp",
        "columns": [
            _okf_col("weapp_id", "Weapp", "id"),
            _okf_col("appid", "Weapp", "appId"),
            _okf_col("weapp_name", "Weapp", "name"),
            _okf_col("(constant=active)", "Weapp", "status"),
            _okf_col("modify_time", "Weapp", "updatedAt"),
        ],
    },
    "ecom_SystemConfig": {
        "industry": "ecom",
        "objectType": "SystemConfig",
        "label": "微商城电商 · SystemConfig",
        "columns": [
            _okf_col("id", "SystemConfig", "id"),
            _okf_col("site_id", "SystemConfig", "siteId"),
            _okf_col("app_module", "SystemConfig", "module"),
            _okf_col("config_key", "SystemConfig", "key"),
            _okf_col("modify_time", "SystemConfig", "updatedAt"),
        ],
    },
    "ecom_ProductReview": {
        "industry": "ecom",
        "objectType": "ProductReview",
        "label": "微商城电商 · ProductReview",
        "columns": [
            _okf_col("evaluate_id", "ProductReview", "id"),
            _okf_col("goods_id", "ProductReview", "productId"),
            _okf_col("member_id", "ProductReview", "memberId"),
            _okf_col("scores", "ProductReview", "score"),
            _okf_col("create_time", "ProductReview", "updatedAt"),
        ],
    },
    "ecom_Payment": {
        "industry": "ecom",
        "objectType": "Payment",
        "label": "微商城电商 · Payment",
        "columns": [
            _okf_col("id", "Payment", "id"),
            _okf_col("relate_id", "Payment", "orderId"),
            _okf_col("out_trade_no", "Payment", "outTradeNo"),
            _okf_col("pay_status", "Payment", "payStatus"),
            _okf_col("pay_time", "Payment", "updatedAt"),
        ],
    },
}


def _okf_mapping_view(payload: dict[str, Any], *, revision: int) -> dict[str, Any]:
    columns = [dict(column) for column in payload.get("columns") or [] if isinstance(column, dict)]
    blocked = [str(column.get("dst") or column.get("src") or "") for column in columns if not column.get("ok")]
    mapped = len(columns) - len(blocked)
    return {
        "industry": str(payload.get("industry") or ""),
        "objectType": str(payload.get("objectType") or ""),
        "label": str(payload.get("label") or ""),
        "columns": columns,
        "revision": revision,
        "coverage": {"mapped": mapped, "total": len(columns), "percent": round(mapped * 100 / len(columns)) if columns else 0},
        "blockedFields": blocked,
        "impact": {
            "requiresRebuild": bool(blocked),
            "affectedObjectType": str(payload.get("objectType") or ""),
            "mappedFieldCount": mapped,
        },
    }


def _okf_type_key(industry: str, object_type: str) -> str:
    return f"okf_mapping:{industry}:{object_type}"


def _okf_required_coverage(
    object_type: str,
    columns: list[dict[str, Any]],
) -> dict[str, int]:
    from aos_api.ecom_core_models import REQUIRED_PROPERTIES

    required = set(REQUIRED_PROPERTIES.get(object_type, frozenset()))
    mapped = {
        str(column.get("dst") or "").split(".")[-1]
        for column in columns
        if column.get("ok")
    }
    mapped_required = len(required & mapped)
    total = len(required)
    return {
        "mapped": mapped_required,
        "total": total,
        "percent": round(mapped_required * 100 / total) if total else 0,
    }


def _okf_type_view(
    payload: dict[str, Any] | None,
    *,
    industry: str,
    object_type: str,
    revision: int,
    source_count: int = 0,
    watermark: Any = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    from aos_api.ecom_core_models import REQUIRED_PROPERTIES

    columns = [
        dict(column)
        for column in (payload or {}).get("columns") or []
        if isinstance(column, dict)
    ]
    required = _okf_required_coverage(object_type, columns)
    blocked = [
        str(column.get("dst") or column.get("src") or "")
        for column in columns
        if not column.get("ok")
    ]
    configured = payload is not None
    return {
        "industry": industry,
        "objectType": object_type,
        "label": str((payload or {}).get("label") or display_name or f"{industry} · {object_type}"),
        "columns": columns,
        "revision": revision,
        "status": "configured" if configured else "unconfigured",
        "coverage": {
            "required": required,
            "optional": {
                "mapped": len(
                    [
                        column
                        for column in columns
                        if column.get("ok")
                        and str(column.get("dst") or "").split(".")[-1]
                        not in set(REQUIRED_PROPERTIES.get(object_type, frozenset()))
                    ]
                ),
                "total": None,
                "percent": None,
                "status": "unknown",
            },
        },
        "blockedFields": blocked,
        "source": {
            "available": source_count > 0,
            "count": source_count,
            "watermark": watermark.isoformat() if hasattr(watermark, "isoformat") else watermark,
        },
        "impact": {
            "requiresRebuild": bool(blocked),
            "affectedObjectType": object_type,
            "mappedRequiredFieldCount": required["mapped"],
        },
    }


def _okf_source_types(principal: Principal) -> list[dict[str, Any]]:
    scope = _scope(principal)
    with connect(scope) as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT o.object_type,MAX(t.name) AS display_name,
                       COUNT(*) AS source_count,MAX(o.source_updated_at) AS watermark
                FROM ecom_object o
                LEFT JOIN meta_object_type t ON t.id=o.object_type
                WHERE o.org_id=%s AND o.workspace_id=%s AND o.deleted_at IS NULL
                GROUP BY o.object_type
                ORDER BY o.object_type
                """,
                scope.key,
            ).fetchall()
        ]


def _get_okf_type_payload(
    industry: str,
    object_type: str,
    principal: Principal,
) -> tuple[dict[str, Any] | None, int]:
    from aos_api.aip_kv_store import get_payload

    scope = _scope(principal)
    stored = get_payload(_okf_type_key(industry, object_type), scope)
    if stored:
        return dict(stored), int(stored.get("revision") or 0)
    # The legacy ecommerce key is an Order compatibility alias only. It is read,
    # never copied or overwritten during detail reads.
    if industry == "ecom" and object_type == "Order":
        legacy = get_payload("okf_mapping:ecom", scope)
        if legacy:
            return dict(legacy), int(legacy.get("revision") or 0)
    # Built-in defaults derived from ec_normalizer.py source field mappings.
    # These give every OT a fully-configured initial mapping so that first-read
    # yields 100% required coverage without manual configuration.  A user PUT
    # always overrides (CAS-protected).
    default = _OKF_DEFAULTS.get(f"{industry}_{object_type}")
    if default:
        return dict(default), 0
    return None, 0


@router.get("/v1/ontology/okf-mappings/{industry}/types")
def get_okf_mapping_types(
    industry: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if industry != "ecom":
        raise ApiError(code="VALIDATION", message="multi-type OKF is available for ecom", status_code=400)
    items: list[dict[str, Any]] = []
    for source in _okf_source_types(principal):
        object_type = str(source["object_type"])
        payload, revision = _get_okf_type_payload(industry, object_type, principal)
        items.append(
            _okf_type_view(
                payload,
                industry=industry,
                object_type=object_type,
                revision=revision,
                source_count=int(source["source_count"]),
                watermark=source.get("watermark"),
                display_name=str(source.get("display_name") or "") or None,
            )
        )
    mapped = sum(item["coverage"]["required"]["mapped"] for item in items)
    total = sum(item["coverage"]["required"]["total"] for item in items)
    unknown = [item["objectType"] for item in items if item["status"] != "configured"]
    overall = {
        "required": {
            "mapped": mapped,
            "total": total,
            "percent": round(mapped * 100 / total) if total else 0,
        },
        "excluded": [],
        "unknown": unknown,
        "complete": bool(total) and mapped == total and not unknown,
        "formula": "sum(mapped required) / sum(composed required) for real source types",
    }
    return {"industry": industry, "items": items, "overall": overall}


@router.get("/v1/ontology/okf-mappings/{industry}/types/{object_type}")
def get_okf_type_mapping(
    industry: str,
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if industry != "ecom":
        raise ApiError(code="VALIDATION", message="multi-type OKF is available for ecom", status_code=400)
    source = next(
        (row for row in _okf_source_types(principal) if row["object_type"] == object_type),
        None,
    )
    payload, revision = _get_okf_type_payload(industry, object_type, principal)
    return _okf_type_view(
        payload,
        industry=industry,
        object_type=object_type,
        revision=revision,
        source_count=int((source or {}).get("source_count") or 0),
        watermark=(source or {}).get("watermark"),
        display_name=str((source or {}).get("display_name") or "") or None,
    )


@router.put("/v1/ontology/okf-mappings/{industry}/types/{object_type}")
def put_okf_type_mapping(
    industry: str,
    object_type: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.ecom_core_models import CORE_OBJECT_TYPES

    if industry != "ecom" or object_type not in CORE_OBJECT_TYPES:
        raise ApiError(code="VALIDATION", message="invalid ecommerce object type", status_code=400)
    columns = body.get("columns")
    if not isinstance(columns, list):
        raise ApiError(code="VALIDATION", message="columns must be a list", status_code=400)
    expected_revision = body.get("expectedRevision")
    if not isinstance(expected_revision, int) or expected_revision < 0:
        raise ApiError(code="OKF_EXPECTED_REVISION_REQUIRED", message="expectedRevision must be a non-negative integer", status_code=428)
    payload = {
        "industry": industry,
        "objectType": object_type,
        "label": str(body.get("label") or f"微商城电商 · {object_type}"),
        "columns": [
            {
                "src": str(column.get("src") or ""),
                "dst": str(column.get("dst") or ""),
                "ok": bool(column.get("ok")),
            }
            for column in columns
            if isinstance(column, dict)
        ],
    }
    scope = _scope(principal)
    key = _okf_type_key(industry, object_type)
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT payload FROM meta_aip_kv WHERE org_id=%s AND project_id=%s AND key=%s FOR UPDATE",
            (*scope.key, key),
        ).fetchone()
        current_payload = dict(row["payload"] or {}) if row else None
        current_revision = int((current_payload or {}).get("revision") or 0)
        if current_revision != expected_revision:
            raise ApiError(
                code="OKF_MAPPING_CAS_CONFLICT",
                message="OKF mapping revision changed",
                status_code=412,
                details={"expected": expected_revision, "actual": current_revision},
            )
        payload["revision"] = current_revision + 1
        conn.execute(
            """
            INSERT INTO meta_aip_kv (org_id,project_id,key,payload,updated_at)
            VALUES (%s,%s,%s,%s::jsonb,NOW())
            ON CONFLICT (org_id,project_id,key) DO UPDATE
              SET payload=EXCLUDED.payload,updated_at=NOW()
            """,
            (*scope.key, key, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    return get_okf_type_mapping(industry, object_type, principal)


@router.get("/v1/ontology/okf-mappings/{industry}")
def get_okf_mapping(
    industry: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    from aos_api.aip_kv_store import get_payload

    key = f"okf_mapping:{industry}"
    stored = get_payload(key, _scope(principal))
    if stored:
        return _okf_mapping_view(stored, revision=int(stored.get("revision") or 0))
    default = _OKF_DEFAULTS.get(f"{industry}_Order") or _OKF_DEFAULTS.get(industry)
    if not default:
        raise ApiError(
            code="NOT_FOUND", message=f"unknown industry: {industry}", status_code=404
        )
    return _okf_mapping_view(dict(default), revision=0)


@router.put("/v1/ontology/okf-mappings/{industry}")
def put_okf_mapping(
    industry: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if f"{industry}_Order" not in _OKF_DEFAULTS and industry not in _OKF_DEFAULTS:
        raise ApiError(code="VALIDATION", message="invalid industry", status_code=400)
    columns = body.get("columns")
    if not isinstance(columns, list):
        raise ApiError(
            code="VALIDATION", message="columns must be a list", status_code=400
        )
    expected_revision = body.get("expectedRevision")
    if not isinstance(expected_revision, int) or expected_revision < 0:
        raise ApiError(code="OKF_EXPECTED_REVISION_REQUIRED", message="expectedRevision must be a non-negative integer", status_code=428)
    payload = {
        "industry": industry,
        "objectType": str(
            body.get("objectType")
            or (_OKF_DEFAULTS.get(f"{industry}_Order", {}).get("objectType"))
            or "Order"
        ),
        "label": str(
            body.get("label")
            or (_OKF_DEFAULTS.get(f"{industry}_Order", {}).get("label"))
            or industry
        ),
        "columns": [
            {
                "src": str(c.get("src") or ""),
                "dst": str(c.get("dst") or ""),
                "ok": bool(c.get("ok")),
            }
            for c in columns
            if isinstance(c, dict)
        ],
    }
    scope = _scope(principal)
    key = f"okf_mapping:{industry}"
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT payload FROM meta_aip_kv WHERE org_id=%s AND project_id=%s AND key=%s FOR UPDATE",
            (*scope.key, key),
        ).fetchone()
        current_payload = dict(row["payload"] or {}) if row else None
        current_revision = int((current_payload or {}).get("revision") or 0)
        if current_revision != expected_revision:
            raise ApiError(
                code="OKF_MAPPING_CAS_CONFLICT",
                message="OKF mapping revision changed",
                status_code=412,
                details={"expected": expected_revision, "actual": current_revision},
            )
        payload["revision"] = current_revision + 1
        conn.execute(
            """
            INSERT INTO meta_aip_kv (org_id,project_id,key,payload,updated_at)
            VALUES (%s,%s,%s,%s::jsonb,NOW())
            ON CONFLICT (org_id,project_id,key) DO UPDATE
              SET payload=EXCLUDED.payload,updated_at=NOW()
            """,
            (*scope.key, key, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    log.info("okf_mapping_put industry=%s revision=%s cols=%s", industry, payload["revision"], len(payload["columns"]))
    return _okf_mapping_view(payload, revision=payload["revision"])


class FunnelRerunIn(BaseModel):
    mode: str = "live"  # live | replacement


@router.post("/v1/funnel/{object_type}/rerun")
def funnel_rerun(
    object_type: str,
    body: FunnelRerunIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """89 · 重跑 Funnel：写 funnel_status + worker 进度快照。"""
    _ = principal
    mode = (body.mode if body else "live") or "live"
    if mode not in {"live", "replacement"}:
        raise ApiError(
            code="VALIDATION", message="mode must be live|replacement", status_code=400
        )
    if mode == "live":
        stage = "hydration"
        worker = [
            {"name": "Changelog", "progress": 1.0},
            {"name": "Merge", "progress": 1.0},
            {"name": "Index", "progress": 1.0},
            {"name": "Hydration", "progress": 1.0},
        ]
    else:
        stage = "replacement"
        worker = [
            {"name": "Changelog", "progress": 1.0},
            {"name": "Merge", "progress": 0.67},
            {"name": "Index", "progress": 0.0},
            {"name": "Hydration", "progress": 0.0},
        ]
    detail = {
        "mode": mode,
        "worker": worker,
        "rerunAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "receiptId": str(uuid.uuid4()),
        "failures": [],
    }
    with connect() as conn:
        result = conn.execute(
            """
            INSERT INTO funnel_status (
              object_type, stage, detail, org_id, project_id
            ) VALUES (%s,%s,%s::jsonb,%s,%s)
            ON CONFLICT (org_id, project_id, object_type) DO UPDATE
              SET stage = EXCLUDED.stage, detail = EXCLUDED.detail
            WHERE funnel_status.org_id=EXCLUDED.org_id
              AND funnel_status.project_id=EXCLUDED.project_id
            """,
            (object_type, stage, json.dumps(detail), *_scope(principal).key),
        )
        if result.rowcount == 0:
            raise ApiError(
                code="TENANT_KEY_CONFLICT",
                message="funnel key belongs to another tenant or legacy scope",
                status_code=409,
            )
        conn.commit()
    log.info("funnel_rerun type=%s mode=%s stage=%s", object_type, mode, stage)
    return {
        "objectType": object_type,
        "stage": stage,
        "mode": mode,
        "detail": detail,
        "receiptId": detail["receiptId"],
        "rerunAt": detail["rerunAt"],
        "stages": worker,
    }
