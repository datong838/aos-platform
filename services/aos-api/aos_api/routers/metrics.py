"""TX.2 — GET /v1/metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from aos_api.auth import Principal, require_principal
from aos_api.metrics import prom_text, snapshot

router = APIRouter(tags=["metrics"])


@router.get("/v1/metrics")
def get_metrics(
    principal: Principal = Depends(require_principal),
    format: str = Query(default="json", alias="format"),
):
    _ = principal
    if format.lower() in ("prom", "prometheus", "text"):
        return Response(content=prom_text(), media_type="text/plain; version=0.0.4; charset=utf-8")
    return snapshot()
