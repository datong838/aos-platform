"""Phase 5 · Pipelines 路由.

pipelines + graph + files + nodes (preview/config/trial-run) + proposals + history.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase5_pipeline_engine import get_engine

router = APIRouter(prefix="/v1/pipelines", tags=["phase5-pipelines"])


# ─────────── Request models ───────────


class CreatePipelineRequest(BaseModel):
    name: str
    description: str = ""
    pipeline_type: str = "ETL"
    status: str = "draft"
    owner: str = "system"
    tags: list[str] = []


class UpdatePipelineRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    pipeline_type: str | None = None
    status: str | None = None
    owner: str | None = None
    tags: list[str] | None = None


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
async def get_graph(pl_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.get_graph(pl_id)
    except KeyError:
        raise HTTPException(404, f"Pipeline {pl_id} not found")


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
        raise HTTPException(404, f"Node {node_id} not found in pipeline {pl_id}")


@router.put("/{pl_id}/nodes/{node_id}/config")
async def update_node_config(pl_id: str, node_id: str, req: UpdateNodeConfigRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        node = eng.update_node_config(pl_id, node_id, req.config)
        return node.model_dump()
    except KeyError:
        raise HTTPException(404, f"Node {node_id} not found in pipeline {pl_id}")


# ─────────── Trial run ───────────


@router.post("/{pl_id}/nodes/{node_id}/trial-run")
async def trial_run(pl_id: str, node_id: str, req: TrialRunRequest | None = None) -> dict[str, Any]:
    eng = get_engine()
    try:
        sample_input = req.sample_input if req else None
        return eng.trial_run(pl_id, node_id, sample_input)
    except KeyError:
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
    eng = get_engine()
    if eng.get_pipeline(pl_id) is None:
        raise HTTPException(404, f"Pipeline {pl_id} not found")
    items = eng.list_history(pl_id)
    return {"items": [h.model_dump() for h in items], "count": len(items)}
