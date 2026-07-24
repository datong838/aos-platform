"""W2-I · Ontology 治理路由：Usage Metrics + Graph Query."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.logging_facade import get_logger
from aos_api.ontology_governance import get_graph_engine, get_usage_engine

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
    maxHops: int = Field(default=6, ge=1, le=8)
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


@router.get("/v1/objects/{object_type}/{object_id}/neighbors/{hops}")
def multi_hop_neighbors(
    object_type: str,
    object_id: str,
    hops: int,
    rel: str | None = None,
    direction: str = Query(default="out", pattern=r"^(out|in|both)$"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#69 · 多跳邻居查询（BFS，1-5 跳）。"""
    _ = principal
    eng = get_graph_engine()
    result = eng.multi_hop(
        object_type, object_id, hops,
        rel=rel, direction=direction,
    )
    log.info("multi_hop src=%s/%s hops=%s nodes=%s",
             object_type, object_id, hops, result["totalNodes"])
    return result


@router.post("/v1/ontology/graph/path")
def shortest_path(
    body: PathQueryIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#69 · 最短路径查询（双向 BFS）。"""
    _ = principal
    eng = get_graph_engine()
    result = eng.shortest_path(
        body.srcType, body.srcId,
        body.dstType, body.dstId,
        max_hops=body.maxHops,
        rels=body.rels,
    )
    log.info("shortest_path found=%s distance=%s explored=%s",
             result["found"], result.get("distance", -1), result["explored"])
    return result


@router.post("/v1/ontology/graph/expand")
def graph_expand(
    body: ExpandQueryIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#69 · 子图扩展（从种子节点向外 N 跳）。"""
    _ = principal
    eng = get_graph_engine()
    seeds = [(s["type"], s["id"]) for s in body.seeds if "type" in s and "id" in s]
    result = eng.expand(
        seeds, body.hops,
        max_nodes=body.maxNodes,
        rels=body.rels,
    )
    log.info("graph_expand seeds=%s hops=%s nodes=%s",
             len(seeds), body.hops, result["totalNodes"])
    return result


@router.post("/v1/ontology/graph/edges")
def upsert_graph_edges_dev(
    body: GraphEdgeBatchIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#69 · 向内存图引擎添加边（测试/脚本化用）。"""
    _ = principal
    eng = get_graph_engine()
    written = 0
    for e in body.edges:
        eng.add_edge(e.rel, e.srcType, e.srcId, e.dstType, e.dstId)
        written += 1
    log.info("graph_edges_add count=%s", written)
    return {"added": written}
