"""W2-A4 · AIP Analyst 查询路由。

POST /v1/aip/analyst/query — body: sql 或 naturalLanguage；返回 columns/rows/durationMs/source。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aos_api.aip_analyst_query import run_analyst_query

router = APIRouter(prefix="/v1/aip/analyst", tags=["aip-analyst"])


class AnalystQueryRequest(BaseModel):
    sql: str | None = Field(default=None, description="SELECT SQL")
    naturalLanguage: str | None = Field(default=None, description="自然语言问句")


@router.post("/query")
def analyst_query(body: AnalystQueryRequest) -> dict[str, Any]:
    try:
        return run_analyst_query(sql=body.sql, natural_language=body.naturalLanguage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
