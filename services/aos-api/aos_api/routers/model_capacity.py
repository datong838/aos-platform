"""Phase 2 · Capacity router — project/user limits + daily usage.

GET /v1/aip/capacity/project-limits        — project-scope limit
PUT /v1/aip/capacity/project-limits        — upsert project-scope limit
GET /v1/aip/capacity/user-limits           — user-scope limit (by ?userId=)
PUT /v1/aip/capacity/user-limits           — upsert user-scope limit
GET /v1/aip/capacity/usage                 — daily usage list
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from aos_api.model_capacity import (
    get_or_default_limit,
    list_usage,
    upsert_limit,
    upsert_usage,
    SCOPE_PROJECT,
    SCOPE_USER,
)

router = APIRouter(prefix="/v1/aip/capacity", tags=["aip-capacity"])


class LimitPutRequest(BaseModel):
    rpmLimit: int = 60
    tpmLimit: int = 60000


class UsageUpsertRequest(BaseModel):
    day: str
    totalRequests: int = 0
    totalTokens: int = 0
    cost: float = 0.0
    peakRpm: int = 0


# ── Project limits ──


@router.get("/project-limits")
def get_project_limits_api(projectId: str | None = Query(None)) -> dict[str, Any]:
    key = projectId or "default"
    return get_or_default_limit(SCOPE_PROJECT, key)


@router.put("/project-limits")
def put_project_limits_api(body: LimitPutRequest, projectId: str | None = Query(None)) -> dict[str, Any]:
    key = projectId or "default"
    return upsert_limit(SCOPE_PROJECT, key, body.model_dump())


# ── User limits ──


@router.get("/user-limits")
def get_user_limits_api(userId: str = Query(...)) -> dict[str, Any]:
    return get_or_default_limit(SCOPE_USER, userId)


@router.put("/user-limits")
def put_user_limits_api(body: LimitPutRequest, userId: str = Query(...)) -> dict[str, Any]:
    return upsert_limit(SCOPE_USER, userId, body.model_dump())


# ── Usage ──


@router.get("/usage")
def list_usage_api(
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    limit: int = Query(30, le=365),
) -> dict[str, Any]:
    items = list_usage(start_date=startDate, end_date=endDate, limit=limit)
    # summary
    total_requests = sum(i["totalRequests"] for i in items)
    total_tokens = sum(i["totalTokens"] for i in items)
    total_cost = round(sum(i["cost"] for i in items), 6)
    peak_rpm = max((i["peakRpm"] for i in items), default=0)
    return {
        "items": items,
        "count": len(items),
        "summary": {
            "totalRequests": total_requests,
            "totalTokens": total_tokens,
            "totalCost": total_cost,
            "peakRpm": peak_rpm,
        },
    }
