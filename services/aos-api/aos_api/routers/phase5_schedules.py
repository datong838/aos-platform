"""Phase 5 · Schedules 路由.

schedules CRUD + run + pause.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase5_pipeline_engine import get_engine

router = APIRouter(prefix="/v1/schedules", tags=["phase5-schedules"])


# ─────────── Request models ───────────


class CreateScheduleRequest(BaseModel):
    name: str
    pipeline_id: str = ""
    trigger_type: str = "cron"
    cron_expr: str = ""
    status: str = "active"
    owner: str = "system"


class UpdateScheduleRequest(BaseModel):
    name: str | None = None
    pipeline_id: str | None = None
    trigger_type: str | None = None
    cron_expr: str | None = None
    status: str | None = None
    owner: str | None = None


# ─────────── Schedules list + create + detail + update ───────────


@router.get("")
async def list_schedules(
    search: str | None = Query(None),
    status: str | None = Query(None),
    trigger_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_schedules(
        search=search, status=status, trigger_type=trigger_type,
        page=page, page_size=page_size,
    )
    return {
        "items": [s.model_dump() for s in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("")
async def create_schedule(req: CreateScheduleRequest) -> dict[str, Any]:
    eng = get_engine()
    sc = eng.create_schedule(**req.model_dump())
    return sc.model_dump()


@router.get("/{sc_id}")
async def get_schedule(sc_id: str) -> dict[str, Any]:
    eng = get_engine()
    sc = eng.get_schedule(sc_id)
    if sc is None:
        raise HTTPException(404, f"Schedule {sc_id} not found")
    return sc.model_dump()


@router.put("/{sc_id}")
async def update_schedule(sc_id: str, req: UpdateScheduleRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        sc = eng.update_schedule(sc_id, **data)
        return sc.model_dump()
    except KeyError:
        raise HTTPException(404, f"Schedule {sc_id} not found")


# ─────────── Run + Pause ───────────


@router.post("/{sc_id}/run")
async def run_schedule(sc_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        run = eng.run_schedule(sc_id)
        return run.model_dump()
    except KeyError:
        raise HTTPException(404, f"Schedule {sc_id} not found")


@router.post("/{sc_id}/pause")
async def pause_schedule(sc_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        sc = eng.pause_schedule(sc_id)
        return sc.model_dump()
    except KeyError:
        raise HTTPException(404, f"Schedule {sc_id} not found")


# ─────────── Schedule runs ───────────


@router.get("/{sc_id}/runs")
async def list_schedule_runs(sc_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_schedule(sc_id) is None:
        raise HTTPException(404, f"Schedule {sc_id} not found")
    items = eng.list_schedule_runs(sc_id)
    return {"items": [r.model_dump() for r in items], "count": len(items)}
