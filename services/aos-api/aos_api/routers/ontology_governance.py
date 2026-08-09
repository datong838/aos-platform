"""W2-I · Ontology 治理路由：Usage Metrics + Graph Query."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.ontology_governance import get_graph_engine, get_usage_engine
from aos_api.ontology_explorer_contracts import GraphQueryDTO, GraphSnapshotDTO
from aos_api.ontology_graph_query import get_authoritative_graph_service
from aos_api.oidc import allow_dev
from aos_api.tenant_scope import TenantScope

router = APIRouter(tags=["ontology-governance"])
log = get_logger("aos-api.ontology_governance")


# ─────────────── #38 Usage Metrics ───────────────

class UsageRecordIn(BaseModel):
    event_type: str = Field(pattern=r"^(read|write|interaction)$")
    user_id: str | None = None
    source: str = "api"
    object_type: str | None = None
    link_type: str | None = None


@router.get("/v1/ontology/usage")
def usage_global(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    """#38 · 全局 Ontology 使用指标（30 天滑动窗口）。"""
    _ = principal
    eng = get_usage_engine()
    metric = eng.get_global()
    log.info("usage_global reads=%s writes=%s active_users=%s",
             metric.reads, metric.writes, metric.active_users)
    return metric.model_dump()


@router.get("/v1/ontology/usage/object-types/{object_type}")
def usage_object_type(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#38 · 指定 Object Type 的使用指标。"""
    _ = principal
    eng = get_usage_engine()
    metric = eng.get_object_type(object_type)
    log.info("usage_otype otype=%s reads=%s", object_type, metric.reads)
    return {"objectType": object_type, **metric.model_dump()}


@router.get("/v1/ontology/usage/link-types/{link_type}")
def usage_link_type(
    link_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#38 · 指定 Link Type 的使用指标。"""
    _ = principal
    eng = get_usage_engine()
    metric = eng.get_link_type(link_type)
    log.info("usage_ltype ltype=%s reads=%s", link_type, metric.reads)
    return {"linkType": link_type, **metric.model_dump()}


@router.post("/v1/ontology/usage/record")
def usage_record(
    body: UsageRecordIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#38 · 手动上报指标事件（测试/外部系统用）。"""
    _ = principal
    eng = get_usage_engine()
    eng.record(
        body.event_type,
        user_id=body.user_id,
        source=body.source,
        object_type=body.object_type,
        link_type=body.link_type,
    )
    log.info("usage_record event=%s source=%s", body.event_type, body.source)
    return {"ok": True}


# ─────────────── #69 Graph Query ───────────────

class PathQueryIn(BaseModel):
    srcType: str
    srcId: str
    dstType: str
    dstId: str
    maxHops: int = Field(default=5, ge=1, le=5)
    rels: list[str] | None = None


class ExpandQueryIn(BaseModel):
    seeds: list[dict[str, str]]
    hops: int = Field(default=2, ge=1, le=5)
    maxNodes: int = Field(default=500, ge=1, le=2000)
    rels: list[str] | None = None


class GraphEdgeIn(BaseModel):
    rel: str
    srcType: str
    srcId: str
    dstType: str
    dstId: str


class GraphEdgeBatchIn(BaseModel):
    edges: list[GraphEdgeIn] = Field(default_factory=list)


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


@router.post("/v1/ontology/graph/query", response_model=GraphSnapshotDTO)
def authoritative_graph_query(
    body: GraphQueryDTO,
    principal: Principal = Depends(require_principal),
) -> GraphSnapshotDTO:
    return get_authoritative_graph_service().query(_scope(principal), body)


@router.get("/v1/objects/{object_type}/{object_id}/neighbors/{hops}")
def multi_hop_neighbors(
    object_type: str,
    object_id: str,
    hops: int,
    rel: str | None = None,
    direction: str = Query(default="out", pattern=r"^(out|in|both)$"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Compatibility projection backed by the authoritative GraphSnapshot service."""
    snapshot = get_authoritative_graph_service().query(
        _scope(principal),
        GraphQueryDTO(
            seeds=[{"objectType": object_type, "objectId": object_id}],
            hops=hops,
            maxNodes=500,
            direction=direction,
            relationTypes=[rel] if rel else [],
        ),
    )
    result = snapshot.model_dump(mode="json")
    result.update({
        "hops": hops,
        "totalNodes": len(snapshot.nodes),
        "nodes": [
            {"type": node.objectType, "id": node.objectId, "depth": node.depth, "key": node.key}
            for node in snapshot.nodes
        ],
    })
    return result


@router.post("/v1/ontology/graph/path")
def shortest_path(
    body: PathQueryIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Shortest path over the same tenant-authoritative domain graph."""
    result = get_authoritative_graph_service().shortest_path(
        _scope(principal),
        source_type=body.srcType,
        source_id=body.srcId,
        target_type=body.dstType,
        target_id=body.dstId,
        max_hops=body.maxHops,
        relation_types=body.rels,
    )
    log.info("shortest_path found=%s distance=%s explored=%s",
             result["found"], result.get("distance", -1), result["explored"])
    return result


@router.post("/v1/ontology/graph/expand")
def graph_expand(
    body: ExpandQueryIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Compatibility expand response backed by GraphSnapshot."""
    seeds = [
        {"objectType": seed["type"], "objectId": seed["id"]}
        for seed in body.seeds if "type" in seed and "id" in seed
    ]
    snapshot = get_authoritative_graph_service().query(
        _scope(principal),
        GraphQueryDTO(
            seeds=seeds,
            hops=body.hops,
            maxNodes=min(body.maxNodes, 500),
            direction="out",
            relationTypes=body.rels or [],
        ),
    )
    result = snapshot.model_dump(mode="json")
    result.update({
        "hops": body.hops,
        "seedCount": len(seeds),
        "totalNodes": len(snapshot.nodes),
        "nodes": [
            {"type": node.objectType, "id": node.objectId, "depth": node.depth, "key": node.key}
            for node in snapshot.nodes
        ],
    })
    return result


@router.post("/v1/ontology/graph/edges")
def upsert_graph_edges_dev(
    body: GraphEdgeBatchIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Legacy test-only in-memory writer; never reachable from a real tenant."""
    if not allow_dev() or principal.org_id != "dev-org":
        raise ApiError(
            code="GRAPH_AUTHORITY_UNAVAILABLE",
            message="legacy in-memory graph writes are disabled for authoritative tenants",
            status_code=409,
        )
    eng = get_graph_engine()
    written = 0
    for e in body.edges:
        eng.add_edge(e.rel, e.srcType, e.srcId, e.dstType, e.dstId)
        written += 1
    log.info("graph_edges_add count=%s", written)
    return {"added": written}
