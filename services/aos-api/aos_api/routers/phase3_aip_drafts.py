"""Phase 3 · AIP Drafts 路由.

GET  /v1/aip/drafts                — Draft 审查任务列表
POST /v1/aip/drafts/{id}/approve   — 批准（状态机 draft→approved）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_drafts_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-drafts"])


class ApproveRequest(BaseModel):
    reviewer: str = ""


@router.get("/drafts")
async def list_drafts(
    status: str | None = Query(None),
    draft_type: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list(status=status, draft_type=draft_type)
    return {"items": [d.model_dump() for d in items], "count": len(items), "stats": eng.stats()}


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, body: ApproveRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        draft = eng.approve(draft_id, reviewer=body.reviewer)
    except KeyError:
        raise HTTPException(404, f"Draft {draft_id} not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "item": draft.model_dump()}


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str, body: dict[str, str]) -> dict[str, Any]:
    eng = get_engine()
    try:
        draft = eng.reject(draft_id, reviewer=body.get("reviewer", ""), reason=body.get("reason", ""))
    except KeyError:
        raise HTTPException(404, f"Draft {draft_id} not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "item": draft.model_dump()}
