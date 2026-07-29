"""Phase 3 · AIP Drafts 路由.

GET  /v1/aip/drafts                      — Draft 审查任务列表
GET  /v1/aip/drafts/{id}                 — 详情（含 timeline）
POST /v1/aip/drafts/{id}/approve         — 批准
POST /v1/aip/drafts/{id}/reject          — 驳回
POST /v1/aip/drafts/{id}/transition      — 通用状态转换（对齐前端状态机）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_drafts_engine import draft_to_api_dict, get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-drafts"])


class ApproveRequest(BaseModel):
    reviewer: str = ""


class TransitionRequest(BaseModel):
    to: str
    actor: str = ""
    comment: str = ""


@router.get("/drafts")
async def list_drafts(
    status: str | None = Query(None),
    draft_type: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list(status=status, draft_type=draft_type)
    return {
        "items": [draft_to_api_dict(d) for d in items],
        "count": len(items),
        "stats": eng.stats(),
    }


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str) -> dict[str, Any]:
    eng = get_engine()
    draft = eng.get(draft_id)
    if draft is None:
        raise HTTPException(404, f"Draft {draft_id} not found")
    return {"ok": True, "item": draft_to_api_dict(draft)}


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, body: ApproveRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        draft = eng.approve(draft_id, reviewer=body.reviewer)
    except KeyError:
        raise HTTPException(404, f"Draft {draft_id} not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "item": draft_to_api_dict(draft), "status": draft.status}


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    eng = get_engine()
    payload = body or {}
    try:
        draft = eng.reject(
            draft_id,
            reviewer=str(payload.get("reviewer", "")),
            reason=str(payload.get("reason", "")),
        )
    except KeyError:
        raise HTTPException(404, f"Draft {draft_id} not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "item": draft_to_api_dict(draft), "status": draft.status}


@router.post("/drafts/{draft_id}/transition")
async def transition_draft(draft_id: str, body: TransitionRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        draft = eng.transition(
            draft_id,
            body.to,
            actor=body.actor,
            comment=body.comment,
        )
    except KeyError:
        raise HTTPException(404, f"Draft {draft_id} not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "item": draft_to_api_dict(draft), "status": draft.status}
