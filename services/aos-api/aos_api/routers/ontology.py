from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.constitution import lint_object_type
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.marking import apply_field_redaction, can_access_object, ensure_object_access

router = APIRouter(tags=["ontology"])
log = get_logger("aos-api.ontology")


def _object_type_properties(conn, object_type: str) -> list[dict[str, Any]]:
    row = conn.execute(
        "SELECT properties FROM meta_object_type WHERE id=%s",
        (object_type,),
    ).fetchone()
    if not row:
        return []
    props = row["properties"]
    return list(props) if isinstance(props, list) else []


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
    return {
        "id": r["id"],
        "name": r["name"],
        "srcType": r["src_type"],
        "dstType": r["dst_type"],
        "rel": r["rel"],
        "cardinality": r["cardinality"],
        "expectedEdges": int(r["expected_edges"]),
        "mdoApproved": bool(r["mdo_approved"]),
        "published": bool(r["published"]),
        "description": r["description"] or "",
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
def list_object_types(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, description, published, properties FROM meta_object_type ORDER BY id"
        ).fetchall()
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
    return {"items": items}


@router.post("/v1/ontology/object-types")
def create_object_type(
    body: ObjectTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
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
            raise ApiError(code="VALIDATION", message="object type exists", status_code=400)
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
    _ = principal
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, description, published, properties
            FROM meta_object_type WHERE id=%s
            """,
            (type_id,),
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="object type not found", status_code=404)
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "published": row["published"],
        "properties": row["properties"],
    }


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
    _ = principal
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
            raise ApiError(code="NOT_FOUND", message="object type not found", status_code=404)
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
    log.info("update_object_type id=%s published=%s props=%s", type_id, body.publish, len(body.properties))
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
def list_link_types(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, src_type, dst_type, rel, cardinality,
                   expected_edges, mdo_approved, published, description
            FROM meta_link_type ORDER BY id
            """
        ).fetchall()
    items = [_row_to_link(r) for r in rows]
    log.info("list_link_types count=%s", len(items))
    return {"items": items}


@router.post("/v1/ontology/link-types")
def create_link_type(
    body: LinkTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    _check_link_scale(expected_edges=body.expectedEdges, mdo_approved=body.mdoApproved)
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_link_type WHERE id=%s", (body.id,)
        ).fetchone()
        if exists:
            raise ApiError(code="VALIDATION", message="link type exists", status_code=400)
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
    """Upsert link instances into graph_edge (scripted twin / VERIFY.2)."""
    _ = principal
    if not body.edges:
        raise ApiError(code="VALIDATION", message="edges required", status_code=400)
    written = 0
    with connect() as conn:
        for e in body.edges:
            conn.execute(
                """
                INSERT INTO graph_edge (src_type, src_id, rel, dst_type, dst_id)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (src_type, src_id, rel, dst_type, dst_id) DO NOTHING
                """,
                (e.srcType, e.srcId, e.rel, e.dstType, e.dstId),
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
    _ = principal
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, src_type, dst_type, rel, cardinality,
                   expected_edges, mdo_approved, published, description
            FROM meta_link_type WHERE id=%s
            """,
            (link_id,),
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="link type not found", status_code=404)
    return _row_to_link(row)


@router.put("/v1/ontology/link-types/{link_id}")
def update_link_type(
    link_id: str,
    body: LinkTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    if body.id != link_id:
        raise ApiError(code="VALIDATION", message="id mismatch", status_code=400)
    _check_link_scale(expected_edges=body.expectedEdges, mdo_approved=body.mdoApproved)
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM meta_link_type WHERE id=%s", (link_id,)
        ).fetchone()
        if not row:
            raise ApiError(code="NOT_FOUND", message="link type not found", status_code=404)
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
    _ = principal
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM meta_link_type WHERE id=%s", (link_id,)
        ).fetchone()
        if not row:
            raise ApiError(code="NOT_FOUND", message="link type not found", status_code=404)
        conn.execute("DELETE FROM meta_link_type WHERE id=%s", (link_id,))
        conn.commit()
    log.info("delete_link_type id=%s", link_id)
    return {"ok": True, "id": link_id}


@router.get("/v1/objects/{object_type}")
def list_objects(
    object_type: str,
    principal: Principal = Depends(require_principal),
    branch: str | None = None,
) -> dict[str, Any]:
    """List instances. ``branch`` selects effective view (89 v2 overlay)."""
    with connect() as conn:
        from aos_api.branch_store import effective_objects, ensure_overlay_table

        ensure_overlay_table(conn)
        prop_defs = _object_type_properties(conn, object_type)
        rows = effective_objects(conn, object_type, branch)
        items = []
        for r in rows:
            if not can_access_object(principal, conn, object_type, r["object_id"]):
                continue
            raw = {"id": r["object_id"], "type": object_type, **(r["props"] or {})}
            items.append(apply_field_redaction(principal, raw, prop_defs, conn=conn))
    out: dict[str, Any] = {"items": items, "total": len(items)}
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
    with connect() as conn:
        from aos_api.branch_store import effective_object, ensure_overlay_table

        ensure_overlay_table(conn)
        ensure_object_access(principal, conn, object_type, object_id)
        prop_defs = _object_type_properties(conn, object_type)
        hit = effective_object(conn, object_type, object_id, branch)
        if not hit:
            raise ApiError(code="NOT_FOUND", message="object not found", status_code=404)
        raw = {"id": object_id, "type": object_type, **(hit["props"] or {})}
        out = apply_field_redaction(principal, raw, prop_defs, conn=conn)
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
    _ = principal
    if not branch:
        raise ApiError(
            code="VALIDATION",
            message="PUT requires ?branch= for overlay writes; production uses Draft",
            status_code=400,
        )
    with connect() as conn:
        from aos_api.branch_store import ensure_overlay_table, upsert_overlay

        ensure_overlay_table(conn)
        ot = conn.execute(
            "SELECT 1 FROM meta_object_type WHERE id=%s", (object_type,)
        ).fetchone()
        if not ot:
            raise ApiError(code="NOT_FOUND", message="object type not found", status_code=404)
        upsert_overlay(conn, branch, object_type, object_id, body.props or {}, op=body.op or "upsert")
        conn.commit()
    log.info("object_overlay_put type=%s id=%s branch=%s op=%s", object_type, object_id, branch, body.op)
    return {"ok": True, "objectType": object_type, "objectId": object_id, "branch": branch, "op": body.op}


@router.get("/v1/objects/{object_type}/{object_id}/neighbors")
def neighbors(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """1-hop graph read — adjacency table interim (AGE blocked, see 26 §阻塞)."""
    _ = principal
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT rel, dst_type, dst_id FROM graph_edge
            WHERE src_type=%s AND src_id=%s
            """,
            (object_type, object_id),
        ).fetchall()
    items = [
        {"rel": r["rel"], "type": r["dst_type"], "id": r["dst_id"]} for r in rows
    ]
    log.info("graph_neighbors src=%s/%s count=%s engine=adjacency", object_type, object_id, len(items))
    return {"items": items, "engine": "adjacency_table"}


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
                "createdAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
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
        raise ApiError(code="NOT_FOUND", message="wiki version not found", status_code=404)
    created = row["created_at"]
    return {
        "id": int(row["id"]),
        "objectType": object_type,
        "objectId": object_id,
        "body": row["body"],
        "draftId": row["draft_id"],
        "createdAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
    }


@router.get("/v1/wiki/{object_type}/{object_id}")
def get_wiki(
    object_type: str,
    object_id: str,
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
        raise ApiError(code="NOT_FOUND", message="wiki not found", status_code=404)
    return {
        "objectType": object_type,
        "objectId": object_id,
        "body": row["body"],
        "orgId": principal.org_id,
        "projectId": principal.project_id,
        "spaceId": wiki_space_id(principal.org_id, principal.project_id),
    }


@router.get("/v1/funnel/{object_type}/status")
def funnel_status(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        row = conn.execute(
            "SELECT stage, detail FROM funnel_status WHERE object_type=%s",
            (object_type,),
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="funnel status missing", status_code=404)
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


@router.get("/v1/ontology/graph-health")
def graph_health(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    """T2.10 + 94 · GH metrics + issues（真悬空边 / 属性键冲突）。"""
    _ = principal
    with connect() as conn:
        types = conn.execute("SELECT COUNT(*) AS c FROM meta_object_type").fetchone()
        objs = conn.execute("SELECT COUNT(*) AS c FROM obj_instance").fetchone()
        edges = conn.execute("SELECT COUNT(*) AS c FROM graph_edge").fetchone()
        orphans = conn.execute(
            """
            SELECT COUNT(*) AS c FROM obj_instance o
            WHERE NOT EXISTS (
              SELECT 1 FROM graph_edge e
              WHERE (e.src_type=o.object_type AND e.src_id=o.object_id)
                 OR (e.dst_type=o.object_type AND e.dst_id=o.object_id)
            )
            """
        ).fetchone()
        dangling = conn.execute(
            """
            SELECT COUNT(*) AS c FROM graph_edge e
            WHERE NOT EXISTS (
              SELECT 1 FROM obj_instance s
              WHERE s.object_type=e.src_type AND s.object_id=e.src_id
            )
            OR NOT EXISTS (
              SELECT 1 FROM obj_instance d
              WHERE d.object_type=e.dst_type AND d.object_id=e.dst_id
            )
            """
        ).fetchone()
        # property key conflicts: instance keys not declared on OT (cap 2000 rows)
        prop_rows = conn.execute(
            """
            SELECT o.object_type, o.object_id, o.props, t.properties
            FROM obj_instance o
            JOIN meta_object_type t ON t.id = o.object_type
            ORDER BY o.object_type, o.object_id
            LIMIT 2000
            """
        ).fetchall()
    dangling_n = int(dangling["c"])
    conflict_n = 0
    conflict_samples: list[str] = []
    for r in prop_rows:
        declared = r["properties"] if isinstance(r["properties"], list) else []
        allowed = {str(p.get("name")) for p in declared if isinstance(p, dict) and p.get("name")}
        allowed |= {"_requiredMarkings"}  # system key
        props = r["props"] if isinstance(r["props"], dict) else {}
        extra = [k for k in props.keys() if k not in allowed]
        if extra:
            conflict_n += 1
            if len(conflict_samples) < 5:
                conflict_samples.append(f"{r['object_type']}/{r['object_id']}:{','.join(extra[:3])}")

    orphan_n = int(orphans["c"])
    metrics = {
        "objectTypes": int(types["c"]),
        "instances": int(objs["c"]),
        "edges": int(edges["c"]),
        "orphanInstances": orphan_n,
        "danglingEdges": dangling_n,
        "propConflicts": conflict_n,
        "archiveCandidates": min(orphan_n, 8) if orphan_n else 0,
        "engine": "adjacency_table",
        "ageAvailable": False,
    }
    score = 100
    issues: list[dict[str, Any]] = []
    if dangling_n > 0:
        score -= min(40, 10 + dangling_n)
        issues.append(
            {
                "code": "GH-01",
                "severity": "bad",
                "object": f"悬空边 ×{dangling_n}",
                "message": "graph_edge 端点在 obj_instance 中不存在",
                "href": "/workshop/graph",
            }
        )
    elif metrics["edges"] == 0:
        score -= 15
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
        score -= min(25, 5 + conflict_n // 2)
        issues.append(
            {
                "code": "GH-02",
                "severity": "warn",
                "object": f"属性冲突 ×{conflict_n}",
                "message": "实例 props 含未声明键 · " + "; ".join(conflict_samples[:3]),
                "href": "/ontology",
            }
        )
    orphan_ratio = orphan_n / max(metrics["instances"], 1)
    if metrics["instances"] and orphan_ratio > 0.8:
        score -= 20
        issues.append(
            {
                "code": "GH-03",
                "severity": "warn",
                "object": f"孤立实例 ×{orphan_n}",
                "message": "无 graph_edge 关联",
                "href": "/ontology",
            }
        )
    elif orphan_n > 0:
        issues.append(
            {
                "code": "GH-03",
                "severity": "warn",
                "object": f"孤立实例 ×{orphan_n}",
                "message": "无 graph_edge 关联",
                "href": "/ontology",
            }
        )
    score = max(0, min(100, score))
    if score < 80:
        issues.append(
            {
                "code": "GH-04",
                "severity": "info",
                "object": "规则",
                "message": f"综合分 {score} < 80，建议 Draft 巡检",
                "href": "/aip/drafts",
            }
        )
    log.info(
        "graph_health score=%s edges=%s dangling=%s conflicts=%s issues=%s",
        score,
        metrics["edges"],
        dangling_n,
        conflict_n,
        len(issues),
    )
    return {"score": score, "metrics": metrics, "issues": issues}


class BranchIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    baseRef: str = "main"


@router.get("/v1/ontology/branches")
def list_branches(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        from aos_api.branch_store import change_count, ensure_overlay_table

        ensure_overlay_table(conn)
        rows = conn.execute(
            "SELECT id, name, base_ref, readonly FROM meta_branch ORDER BY id"
        ).fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "baseRef": r["base_ref"],
                    "readonly": r["readonly"],
                    "changeCount": change_count(conn, r["id"]),
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
        raise ApiError(code="VALIDATION", message="id must be alphanumeric/_/-", status_code=400)
    with connect() as conn:
        from aos_api.branch_store import ensure_overlay_table

        ensure_overlay_table(conn)
        exists = conn.execute("SELECT 1 FROM meta_branch WHERE id=%s", (bid,)).fetchone()
        if exists:
            raise ApiError(code="VALIDATION", message=f"branch exists: {bid}", status_code=400)
        base = body.baseRef.strip() or "main"
        if base not in {"main", "master"}:
            base_row = conn.execute("SELECT 1 FROM meta_branch WHERE id=%s", (base,)).fetchone()
            if not base_row:
                raise ApiError(code="VALIDATION", message=f"baseRef not found: {base}", status_code=400)
        conn.execute(
            """
            INSERT INTO meta_branch (id, name, base_ref, readonly)
            VALUES (%s,%s,%s,FALSE)
            """,
            (bid, body.name.strip(), base),
        )
        conn.commit()
    log.info("branch_created id=%s base=%s", bid, body.baseRef)
    return {"id": bid, "name": body.name.strip(), "baseRef": base, "readonly": False, "changeCount": 0}


class CheckoutIn(BaseModel):
    objectType: str = Field(min_length=1)
    objectId: str = Field(min_length=1)
    patch: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/ontology/branches/{branch_id}/diff")
def branch_diff(
    branch_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        from aos_api.branch_store import diff_branch, ensure_overlay_table

        ensure_overlay_table(conn)
        return diff_branch(conn, branch_id)


@router.post("/v1/ontology/branches/{branch_id}/merge")
def branch_merge(
    branch_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        from aos_api.branch_store import ensure_overlay_table, merge_branch

        ensure_overlay_table(conn)
        out = merge_branch(conn, branch_id)
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
    _ = principal
    with connect() as conn:
        from aos_api.branch_store import checkout_object, ensure_overlay_table

        ensure_overlay_table(conn)
        out = checkout_object(conn, branch_id, body.objectType, body.objectId, body.patch or None)
        conn.commit()
    log.info(
        "branch_checkout branch=%s type=%s id=%s",
        branch_id,
        body.objectType,
        body.objectId,
    )
    return {"ok": True, "branchId": branch_id, **out}


_OKF_DEFAULTS: dict[str, dict[str, Any]] = {
    "ecom": {
        "industry": "ecom",
        "objectType": "WorkOrder",
        "label": "跨境电商 · WorkOrder",
        "columns": [
            {"src": "order_id", "dst": "WorkOrder.id", "ok": True},
            {"src": "title", "dst": "WorkOrder.title", "ok": True},
            {"src": "status", "dst": "WorkOrder.status", "ok": True},
            {"src": "site", "dst": "WorkOrder.site", "ok": True},
        ],
    },
    "env": {
        "industry": "env",
        "objectType": "Pollutant",
        "label": "环科院 · Pollutant",
        "columns": [
            {"src": "pollutant_id", "dst": "Pollutant.id", "ok": True},
            {"src": "name", "dst": "Pollutant.name", "ok": True},
            {"src": "level", "dst": "Pollutant.level", "ok": False},
        ],
    },
    "bio": {
        "industry": "bio",
        "objectType": "Batch",
        "label": "生物 · Batch",
        "columns": [
            {"src": "batch_id", "dst": "Batch.id", "ok": True},
            {"src": "sku", "dst": "Batch.sku", "ok": True},
            {"src": "qty", "dst": "Batch.qty", "ok": False},
        ],
    },
}


@router.get("/v1/ontology/okf-mappings/{industry}")
def get_okf_mapping(
    industry: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    from aos_api.aip_kv_store import get_payload

    key = f"okf_mapping:{industry}"
    stored = get_payload(key)
    if stored:
        return stored
    default = _OKF_DEFAULTS.get(industry)
    if not default:
        raise ApiError(code="NOT_FOUND", message=f"unknown industry: {industry}", status_code=404)
    return dict(default)


@router.put("/v1/ontology/okf-mappings/{industry}")
def put_okf_mapping(
    industry: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    from aos_api.aip_kv_store import put_payload

    if industry not in _OKF_DEFAULTS and not str(industry).strip():
        raise ApiError(code="VALIDATION", message="invalid industry", status_code=400)
    columns = body.get("columns")
    if not isinstance(columns, list):
        raise ApiError(code="VALIDATION", message="columns must be a list", status_code=400)
    payload = {
        "industry": industry,
        "objectType": str(body.get("objectType") or _OKF_DEFAULTS.get(industry, {}).get("objectType") or "WorkOrder"),
        "label": str(body.get("label") or _OKF_DEFAULTS.get(industry, {}).get("label") or industry),
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
    put_payload(f"okf_mapping:{industry}", payload)
    log.info("okf_mapping_put industry=%s cols=%s", industry, len(payload["columns"]))
    return payload


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
        raise ApiError(code="VALIDATION", message="mode must be live|replacement", status_code=400)
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
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO funnel_status (object_type, stage, detail)
            VALUES (%s,%s,%s::jsonb)
            ON CONFLICT (object_type) DO UPDATE
              SET stage = EXCLUDED.stage, detail = EXCLUDED.detail
            """,
            (object_type, stage, json.dumps(detail)),
        )
        conn.commit()
    log.info("funnel_rerun type=%s mode=%s stage=%s", object_type, mode, stage)
    return {"objectType": object_type, "stage": stage, "mode": mode, "detail": detail, "stages": worker}
