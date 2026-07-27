"""Phase 4 · Ontology Links 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aos_api.ontology_link_engine import get_link_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-links"])


class UpdateLinkRequest(BaseModel):
    properties: dict[str, Any] | None = None


@router.get("/links/{link_id}")
async def get_link(link_id: str) -> dict[str, Any]:
    eng = get_link_engine()
    # 既支持 link type 也支持 link instance
    lt = eng.get_link_type(link_id)
    if lt is not None:
        return {"kind": "link_type", **lt.model_dump()}
    li = eng.get_link(link_id)
    if li is not None:
        return {"kind": "link_instance", **li.model_dump()}
    raise HTTPException(404, f"Link {link_id} not found")


@router.put("/links/{link_id}")
async def update_link(link_id: str, req: UpdateLinkRequest) -> dict[str, Any]:
    eng = get_link_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        # 优先更新 instance，再尝试 link type
        li = eng.get_link(link_id)
        if li is not None:
            updated = eng.update_link(link_id, **data)
            return {"kind": "link_instance", **updated.model_dump()}
        lt = eng.get_link_type(link_id)
        if lt is not None:
            updated = eng.update_link_type(link_id, **data)
            return {"kind": "link_type", **updated.model_dump()}
        raise HTTPException(404, f"Link {link_id} not found")
    except KeyError:
        raise HTTPException(404, f"Link {link_id} not found")
