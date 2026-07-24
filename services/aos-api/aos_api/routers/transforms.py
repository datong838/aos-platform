"""W1-8 · Transform 算子库 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.scalar_functions import list_scalar_functions, SCALAR_FN_CATEGORIES
from aos_api.transform_ops import (
    TransformError,
    apply_pipeline,
    apply_transform,
    list_op_catalog,
    register_transform,
    TRANSFORM_REGISTRY,
)

router = APIRouter(tags=["transforms"])


class TransformRequest(BaseModel):
    op: str
    rows: list[dict[str, Any]]
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineRequest(BaseModel):
    rows: list[dict[str, Any]]
    steps: list[dict[str, Any]]


def _map_error(err: TransformError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


@router.get("/v1/transforms")
def list_transforms():
    return {
        "ops": list(TRANSFORM_REGISTRY.keys()),
        "catalog": [m.model_dump() for m in list_op_catalog()],
    }


class RegisterOpRequest(BaseModel):
    name: str
    description: str = ""
    config_schema: dict[str, Any] = Field(default_factory=dict)
    code: str


@router.post("/v1/transforms/register")
def register_custom_op(req: RegisterOpRequest):
    """运行时注册自定义算子（exec 定义 transform(rows, config)）。"""
    sandbox_ns: dict[str, Any] = {"__builtins__": {}}
    try:
        exec(req.code, sandbox_ns)
    except Exception as err:
        raise ApiError(code="OP_CODE_INVALID", message=f"算子代码解析失败：{err}", status_code=400) from err
    fn = sandbox_ns.get("transform")
    if not callable(fn):
        raise ApiError(code="OP_CODE_INVALID", message="代码需定义 transform(rows, config) 函数", status_code=400)
    register_transform(req.name, description=req.description, config_schema=req.config_schema)(fn)
    return {"name": req.name, "registered": True}


@router.post("/v1/transforms/apply")
def apply_single(req: TransformRequest):
    try:
        result = apply_transform(req.op, req.rows, req.config)
    except TransformError as err:
        raise _map_error(err) from err
    return {"result": result, "count": len(result)}


@router.post("/v1/transforms/pipeline")
def apply_transform_pipeline(req: PipelineRequest):
    try:
        result = apply_pipeline(req.rows, req.steps)
    except TransformError as err:
        raise _map_error(err) from err
    return {"result": result, "count": len(result)}


@router.get("/v1/transforms/functions")
def list_scalar_fns():
    """W2-#5 · 返回所有标量函数目录（含分类信息，50+ 函数）。"""
    return {
        "categories": SCALAR_FN_CATEGORIES,
        "functions": list_scalar_functions(),
        "total": sum(len(v) for v in SCALAR_FN_CATEGORIES.values()),
    }
