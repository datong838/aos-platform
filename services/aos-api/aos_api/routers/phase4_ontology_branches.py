"""Phase 4 · Ontology Branches + Graph Health 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.ontology_engine import get_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-branches"])


class CreateBranchRequest(BaseModel):
    name: str
    parent_branch: str = "main"
    description: str = ""
    created_by: str = "system"


@router.get("/branches")
async def list_branches(status: str | None = Query(None)) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_branches(status=status)
    return {"items": [b.model_dump() for b in items], "count": len(items)}


@router.post("/branches")
async def create_branch(req: CreateBranchRequest) -> dict[str, Any]:
    eng = get_engine()
    br = eng.create_branch(**req.model_dump())
    return br.model_dump()


@router.get("/graph-health")
async def graph_health() -> dict[str, Any]:
    eng = get_engine()
    return eng.graph_health()
