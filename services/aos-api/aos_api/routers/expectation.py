"""W2-#15 · Expectation 数据期望 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.expectation import (
    Expectation,
    ExpectationEngine,
    ExpectationError,
    ExpectationType,
    get_engine,
)

router = APIRouter(tags=["expectations"])


class CreateExpectationRequest(BaseModel):
    name: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    severity: str = "error"
    enabled: bool = True


class CheckRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


def _map_error(err: ExpectationError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/expectations")
def create_expectation(req: CreateExpectationRequest):
    """创建数据期望。"""
    try:
        exp_type = ExpectationType(req.type)
    except ValueError:
        valid = [t.value for t in ExpectationType]
        raise ApiError(
            code="UNKNOWN_TYPE",
            message=f"未知期望类型 {req.type!r}，可用：{valid}",
            status_code=400,
        ) from None

    exp = Expectation(
        name=req.name,
        type=exp_type,
        config=req.config,
        severity=req.severity,
        enabled=req.enabled,
    )
    return get_engine().create(exp).model_dump()


@router.get("/v1/expectations")
def list_expectations():
    return {"expectations": [e.model_dump() for e in get_engine().list_all()]}


@router.get("/v1/expectations/{eid}")
def get_expectation(eid: str):
    exp = get_engine().get(eid)
    if exp is None:
        raise ApiError(code="NOT_FOUND", message=f"期望 {eid!r} 不存在", status_code=404)
    return exp.model_dump()


@router.delete("/v1/expectations/{eid}")
def delete_expectation(eid: str):
    deleted = get_engine().delete(eid)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message=f"期望 {eid!r} 不存在", status_code=404)
    return {"deleted": eid}


@router.post("/v1/expectations/{eid}/check")
def check_expectation(eid: str, req: CheckRequest):
    """执行单个期望检查。"""
    exp = get_engine().get(eid)
    if exp is None:
        raise ApiError(code="NOT_FOUND", message=f"期望 {eid!r} 不存在", status_code=404)
    result = get_engine().check(exp, req.rows)
    return result.model_dump()


@router.post("/v1/expectations/check-all")
def check_all_expectations(req: CheckRequest):
    """执行所有已启用的期望检查。"""
    engine = get_engine()
    results = engine.check_all(engine.list_all(), req.rows)
    return {
        "results": [r.model_dump() for r in results],
        "all_passed": all(r.passed for r in results),
        "has_blocking": engine.has_blocking_failure(results),
    }
