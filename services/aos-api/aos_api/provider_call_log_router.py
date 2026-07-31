"""Provider Call Log Router — 222plan Phase A.

供应商调用日志 API：GET（列表）+ GET /stats（统计）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from aos_api.provider_call_log import get_call_log_engine

router = APIRouter(prefix="/api/models/providers", tags=["model-provider-call-logs"])

@router.get("/{provider_id}/logs")
def list_logs(
    provider_id: str,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    engine = get_call_log_engine()
    logs = engine.list_logs(
        provider_id, status_filter=status, limit=limit, offset=offset
    )
    return {
        "items": [l.model_dump() for l in logs],
        "total": len(engine._store.get(provider_id, [])),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{provider_id}/logs/stats")
def get_stats(provider_id: str) -> dict[str, Any]:
    return get_call_log_engine().get_stats(provider_id)
