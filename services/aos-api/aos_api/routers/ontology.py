from __future__ import annotations

import json
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
) -> dict[str, Any]:
    with connect() as conn:
        prop_defs = _object_type_properties(conn, object_type)
        rows = conn.execute(
            "SELECT object_id, props FROM obj_instance WHERE object_type=%s ORDER BY object_id",
            (object_type,),
        ).fetchall()
        items = []
        for r in rows:
            if not can_access_object(principal, conn, object_type, r["object_id"]):
                continue
            raw = {"id": r["object_id"], "type": object_type, **(r["props"] or {})}
            items.append(apply_field_redaction(principal, raw, prop_defs, conn=conn))
    return {"items": items, "total": len(items)}


@router.get("/v1/objects/{object_type}/{object_id}")
def get_object(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    with connect() as conn:
        ensure_object_access(principal, conn, object_type, object_id)
        prop_defs = _object_type_properties(conn, object_type)
        row = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
        if not row:
            raise ApiError(code="NOT_FOUND", message="object not found", status_code=404)
        raw = {"id": object_id, "type": object_type, **(row["props"] or {})}
        return apply_field_redaction(principal, raw, prop_defs, conn=conn)


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


@router.get("/v1/wiki/{object_type}/{object_id}")
def get_wiki(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        row = conn.execute(
            "SELECT body FROM wiki_page WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="wiki not found", status_code=404)
    return {"objectType": object_type, "objectId": object_id, "body": row["body"]}


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
    """T2.10 — GH metrics (≠ L1 health). Adjacency engine until AGE."""
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
    metrics = {
        "objectTypes": int(types["c"]),
        "instances": int(objs["c"]),
        "edges": int(edges["c"]),
        "orphanInstances": int(orphans["c"]),
        "engine": "adjacency_table",
        "ageAvailable": False,
    }
    score = 100
    if metrics["instances"] and metrics["orphanInstances"] / max(metrics["instances"], 1) > 0.8:
        score -= 20
    if metrics["edges"] == 0:
        score -= 30
    log.info("graph_health score=%s edges=%s", score, metrics["edges"])
    return {"score": score, "metrics": metrics}


@router.get("/v1/ontology/branches")
def list_branches(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, base_ref, readonly FROM meta_branch ORDER BY id"
        ).fetchall()
    return {
        "items": [
            {
                "id": r["id"],
                "name": r["name"],
                "baseRef": r["base_ref"],
                "readonly": r["readonly"],
            }
            for r in rows
        ]
    }
