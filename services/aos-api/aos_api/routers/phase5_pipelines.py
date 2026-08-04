"""Phase 5 · Pipelines 路由.

pipelines + graph + files + nodes (preview/config/trial-run) + proposals + history.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/pipelines",
    tags=["phase5-pipelines"],
    dependencies=[Depends(require_principal)],
)


# ─────────── Request models ───────────


class CreatePipelineRequest(BaseModel):
    name: str
    description: str = ""
    pipeline_type: str = "ETL"
    status: str = "draft"
    owner: str = "system"
    tags: list[str] = []
    executor_id: str = ""


class UpdatePipelineRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    pipeline_type: str | None = None
    status: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    executor_id: str | None = None
    write_mode: str | None = None


class GraphNodeRequest(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    node_type: str = Field(default="transform", min_length=1, max_length=80)
    position_x: float = 0.0
    position_y: float = 0.0
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="idle", max_length=80)


class GraphEdgeRequest(BaseModel):
    id: str | None = Field(default=None, max_length=160)
    source_node_id: str = Field(min_length=1, max_length=160)
    target_node_id: str = Field(min_length=1, max_length=160)
    label: str = Field(default="", max_length=240)


class ReplaceGraphRequest(BaseModel):
    nodes: list[GraphNodeRequest] = Field(default_factory=list, max_length=300)
    edges: list[GraphEdgeRequest] = Field(default_factory=list, max_length=1200)
    pipeline_type: str | None = Field(default=None, max_length=80)
    write_mode: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=240)


class UpdateNodeConfigRequest(BaseModel):
    config: dict[str, Any]


class TrialRunRequest(BaseModel):
    sample_input: dict[str, Any] | None = None


class CreateProposalRequest(BaseModel):
    title: str
    description: str = ""
    proposed_by: str = "system"
    diff_summary: str = ""


# ─────────── Pipelines list + detail + update ───────────


@router.get("")
async def list_pipelines(
    search: str | None = Query(None),
    status: str | None = Query(None),
    pipeline_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_pipelines(
        search=search, status=status, pipeline_type=pipeline_type,
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
    )
    return {
        "items": [p.model_dump() for p in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("")
async def create_pipeline(req: CreatePipelineRequest) -> dict[str, Any]:
    eng = get_engine()
    pl = eng.create_pipeline(**req.model_dump())
    return pl.model_dump()


@router.get("/{pl_id}")
async def get_pipeline(pl_id: str) -> dict[str, Any]:
    eng = get_engine()
    pl = eng.get_pipeline(pl_id)
    if pl is None:
        raise HTTPException(404, f"Pipeline {pl_id} not found")
    return pl.model_dump()


@router.put("/{pl_id}")
async def update_pipeline(pl_id: str, req: UpdatePipelineRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        pl = eng.update_pipeline(pl_id, **data)
        return pl.model_dump()
    except KeyError:
        raise HTTPException(404, f"Pipeline {pl_id} not found")


# ─────────── Graph ───────────


@router.get("/{pl_id}/graph")
async def get_graph(
    pl_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    """Return DAG graph; unknown wave_ext pipeline ids get a demo 3-node linear graph."""
    eng = get_engine()
    try:
        return eng.get_graph(TenantScope(principal.org_id, principal.project_id), pl_id)
    except KeyError:
        # W3-C6 · demo fallback for UI pipeline ids outside phase5 store
        n_src = {"id": f"demo-src-{pl_id}", "pipeline_id": pl_id, "name": "source", "node_type": "source",
                 "position_x": 60, "position_y": 60, "config": {}, "status": "idle"}
        n_xf = {"id": f"demo-xf-{pl_id}", "pipeline_id": pl_id, "name": "transform", "node_type": "transform",
                "position_x": 300, "position_y": 60, "config": {"expression": "row", "filter": ""}, "status": "idle"}
        n_sink = {"id": f"demo-sink-{pl_id}", "pipeline_id": pl_id, "name": "sink", "node_type": "sink",
                  "position_x": 540, "position_y": 60, "config": {}, "status": "idle"}
        return {
            "pipeline_id": pl_id,
            "nodes": [n_src, n_xf, n_sink],
            "edges": [
                {"id": f"demo-e1-{pl_id}", "pipeline_id": pl_id, "source_node_id": n_src["id"], "target_node_id": n_xf["id"], "label": ""},
                {"id": f"demo-e2-{pl_id}", "pipeline_id": pl_id, "source_node_id": n_xf["id"], "target_node_id": n_sink["id"], "label": ""},
            ],
            "node_count": 3,
            "edge_count": 2,
            "pipeline_type": "Batch",
            "write_mode": "SNAPSHOT",
            "demo": True,
        }


@router.put("/{pl_id}/graph")
async def replace_graph(
    pl_id: str,
    req: ReplaceGraphRequest,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    """Persist the complete canvas graph after validating it as a DAG."""
    eng = get_engine()
    try:
        result = eng.replace_graph(
            TenantScope(principal.org_id, principal.project_id),
            pl_id,
            [node.model_dump() for node in req.nodes],
            [edge.model_dump(exclude_none=True) for edge in req.edges],
            pipeline_type=req.pipeline_type,
            write_mode=req.write_mode,
            name=req.name,
        )
        pipeline = eng.get_pipeline(pl_id)
        return {
            **result,
            "pipeline_type": pipeline.pipeline_type if pipeline else req.pipeline_type,
            "write_mode": pipeline.write_mode if pipeline else req.write_mode,
            "demo": False,
            "persisted": True,
        }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# ─────────── Files ───────────


@router.get("/{pl_id}/files")
async def get_files(pl_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return {"tree": eng.get_files(pl_id)}
    except KeyError:
        raise HTTPException(404, f"Pipeline {pl_id} not found")


# ─────────── Node preview ───────────


@router.get("/{pl_id}/nodes/{node_id}/preview")
async def preview_node(
    pl_id: str, node_id: str, limit: int = Query(20, ge=1, le=200),
) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.preview_node(pl_id, node_id, limit=limit)
    except KeyError:
        raise HTTPException(404, f"Node {node_id} not found in pipeline {pl_id}")


# ─────────── Node config ───────────


@router.get("/{pl_id}/nodes/{node_id}/config")
async def get_node_config(pl_id: str, node_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.get_node_config(pl_id, node_id)
    except KeyError:
        # W3-C6 · demo config for canvas transform panel
        if node_id.startswith("demo-"):
            return {
                "pipeline_id": pl_id,
                "node_id": node_id,
                "config": {"expression": "row", "filter": ""},
                "demo": True,
            }
        raise HTTPException(404, f"Node {node_id} not found in pipeline {pl_id}")


@router.put("/{pl_id}/nodes/{node_id}/config")
async def update_node_config(pl_id: str, node_id: str, req: UpdateNodeConfigRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        node = eng.update_node_config(pl_id, node_id, req.config)
        return node.model_dump()
    except KeyError:
        if node_id.startswith("demo-"):
            raise HTTPException(409, "Save the demo graph before updating node configuration")
        raise HTTPException(404, f"Node {node_id} not found in pipeline {pl_id}")


# ─────────── Trial run ───────────


@router.post("/{pl_id}/nodes/{node_id}/trial-run")
async def trial_run(pl_id: str, node_id: str, req: TrialRunRequest | None = None) -> dict[str, Any]:
    eng = get_engine()
    try:
        sample_input = req.sample_input if req else None
        return eng.trial_run(pl_id, node_id, sample_input)
    except KeyError:
        if node_id.startswith("demo-"):
            import time as _time
            now = _time.time()
            return {
                "pipeline_id": pl_id,
                "node_id": node_id,
                "mode": "demo",
                "status": "unsupported",
                "started_at": now,
                "finished_at": now,
                "duration_ms": 0,
                "executor_id": "",
                "input_ref": "",
                "output_ref": "",
                "rows_read": 0,
                "rows_written": 0,
                "lineage_ref": "",
                "quality_ref": "",
                "error_code": "DEMO_EXECUTION_UNSUPPORTED",
                "error_message": "demo pipeline does not execute live data",
                "latency_ms": 0,
                "output_rows": [],
                "ran_at": now,
                "demo": True,
            }
        raise HTTPException(404, f"Node {node_id} not found in pipeline {pl_id}")


# ─────────── Proposals ───────────


@router.get("/{pl_id}/proposals")
async def list_proposals(
    pl_id: str, status: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_pipeline(pl_id) is None:
        raise HTTPException(404, f"Pipeline {pl_id} not found")
    items = eng.list_proposals(pl_id, status=status)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.post("/{pl_id}/proposals")
async def create_proposal(pl_id: str, req: CreateProposalRequest) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_pipeline(pl_id) is None:
        raise HTTPException(404, f"Pipeline {pl_id} not found")
    pp = eng.create_proposal(pipeline_id=pl_id, **req.model_dump())
    return pp.model_dump()


@router.post("/{pl_id}/proposals/{pp_id}/discard")
async def discard_proposal(pl_id: str, pp_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        pp = eng.discard_proposal(pl_id, pp_id)
        return pp.model_dump()
    except KeyError:
        raise HTTPException(404, f"Proposal {pp_id} not found in pipeline {pl_id}")


@router.post("/{pl_id}/proposals/{pp_id}/merge")
async def merge_proposal(pl_id: str, pp_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        pp = eng.merge_proposal(pl_id, pp_id)
        return pp.model_dump()
    except KeyError:
        raise HTTPException(404, f"Proposal {pp_id} not found in pipeline {pl_id}")


# ─────────── History ───────────


@router.get("/{pl_id}/history")
async def list_history(pl_id: str) -> dict[str, Any]:
    """Return run/edit history; unknown ids get demo entries (W3-C6)."""
    import time as _time

    eng = get_engine()
    if eng.get_pipeline(pl_id) is None:
        now = _time.time()
        items = [
            {"id": f"ph-demo-1-{pl_id}", "pipeline_id": pl_id, "action": "created", "actor": "system",
             "detail": "演示路径 · 管道创建（phase5 无此 id）", "created_at": now - 86400},
            {"id": f"ph-demo-2-{pl_id}", "pipeline_id": pl_id, "action": "deployed", "actor": "system",
             "detail": "演示路径 · 最近一次部署", "created_at": now - 3600},
            {"id": f"ph-demo-3-{pl_id}", "pipeline_id": pl_id, "action": "run", "actor": "system",
             "detail": "演示路径 · 不执行真实数据", "created_at": now - 600},
        ]
        return {"items": items, "count": len(items), "demo": True}
    items = eng.list_history(pl_id)
    return {"items": [h.model_dump() for h in items], "count": len(items), "demo": False}
