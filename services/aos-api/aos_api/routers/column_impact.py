"""W2-AG · 列级影响分析路由：#109 ColumnImpactEngine 增量补丁."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.column_impact import (
    ColumnImpactError,
    ColumnImpactRule,
    get_impact_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["column-impact"])
log = get_logger("aos-api.column-impact")


def _map_err(err: ColumnImpactError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #109 Column Impact Rule ════════════════════

class ColumnImpactRuleIn(BaseModel):
    source_dataset_rid: str = Field(min_length=1)
    source_column: str = Field(min_length=1)
    downstream_datasets: list[str] = Field(default_factory=list)
    downstream_columns: list[str] = Field(default_factory=list)
    transform_expr: str = ""


class AnalyzeImpactIn(BaseModel):
    source_dataset_rid: str = Field(min_length=1)
    source_column: str = Field(min_length=1)


@router.post("/v1/column-impact/rules")
def register_rule(
    body: ColumnImpactRuleIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#109 · 注册列级影响规则。"""
    _ = principal
    try:
        rule = get_impact_engine().register(ColumnImpactRule(**body.model_dump()))
    except ColumnImpactError as exc:
        raise _map_err(exc) from exc
    return {"item": rule.model_dump()}


@router.get("/v1/column-impact/rules")
def list_rules(
    source_dataset_rid: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#109 · 规则列表。"""
    _ = principal
    items = get_impact_engine().list(source_dataset_rid=source_dataset_rid)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/column-impact/rules/{rule_id}")
def get_rule(
    rule_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#109 · 单条规则。"""
    _ = principal
    try:
        return {"item": get_impact_engine().get(rule_id).model_dump()}
    except ColumnImpactError as exc:
        raise _map_err(exc) from exc


@router.delete("/v1/column-impact/rules/{rule_id}")
def delete_rule(
    rule_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#109 · 删除规则。"""
    _ = principal
    ok = get_impact_engine().delete(rule_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"规则 {rule_id} 不存在", status_code=404)
    return {"id": rule_id, "deleted": True}


@router.post("/v1/column-impact/analyze")
def analyze_impact(
    body: AnalyzeImpactIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#109 · 列级影响分析（BFS）。"""
    _ = principal
    try:
        result = get_impact_engine().analyze_impact(
            body.source_dataset_rid, body.source_column,
        )
    except ColumnImpactError as exc:
        raise _map_err(exc) from exc
    return {"item": result.model_dump()}
