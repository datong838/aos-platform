"""TX.2 — GET /v1/metrics + AIP observability summary/traces (W2-A5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from aos_api.aip_observability import build_summary, build_traces
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


@router.get("/v1/aip/observability/summary")
def get_observability_summary(
    principal: Principal = Depends(require_principal),
    range: str = Query(default="1h", alias="range"),
):
    """Overview KPIs + trend from in-process metrics samples (W2-A5)."""
    _ = principal
    allowed = {"1h", "6h", "24h", "7d"}
    range_key = range if range in allowed else "1h"
    return build_summary(range_key)


@router.get("/v1/aip/observability/traces")
def get_observability_traces(
    principal: Principal = Depends(require_principal),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Sampled trace rows derived from HTTP path counters (W2-A5)."""
    _ = principal
    return build_traces(limit)
