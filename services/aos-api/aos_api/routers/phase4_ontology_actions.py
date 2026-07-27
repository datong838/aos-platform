"""Phase 4 · Ontology Actions 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aos_api.ontology_action_engine import get_action_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-actions"])


class UpdateActionRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    body: str | None = None
    status: str | None = None
    category: str | None = None


@router.get("/actions/{action_id}")
async def get_action(action_id: str) -> dict[str, Any]:
    eng = get_action_engine()
    a = eng.get_action(action_id)
    if a is None:
        raise HTTPException(404, f"Action {action_id} not found")
    return a.model_dump()


@router.put("/actions/{action_id}")
async def update_action(action_id: str, req: UpdateActionRequest) -> dict[str, Any]:
    eng = get_action_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        a = eng.update_action(action_id, **data)
        return a.model_dump()
    except KeyError:
        raise HTTPException(404, f"Action {action_id} not found")
