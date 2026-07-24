"""W1-18 · OMA Function Type 视图 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.function_type_view import (
    CodeLocation,
    FunctionTypeError,
    get_registry,
)

router = APIRouter(tags=["oma-function-types"])


class CodeLocationRequest(BaseModel):
    repo: str = ""
    path: str = ""
    line: int = 0
    url: str = ""


class RecordUsageRequest(BaseModel):
    used_in: str
    used_in_kind: str = "action"


class RecordVersionRequest(BaseModel):
    snapshot: dict
    recorded_by: str = ""


def _map_error(err: FunctionTypeError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.get("/v1/oma/function-types")
def list_function_types():
    views = get_registry().aggregate_all()
    return {"function_types": [v.model_dump() for v in views], "count": len(views)}


@router.get("/v1/oma/function-types/{name}")
def get_function_type(name: str):
    try:
        return get_registry().get_view(name).model_dump()
    except FunctionTypeError as err:
        raise _map_error(err) from err


@router.get("/v1/oma/function-types/{name}/usage")
def get_usage(name: str):
    records = get_registry().get_usage(name)
    return {"function_name": name, "usage": [r.model_dump() for r in records]}


@router.get("/v1/oma/function-types/{name}/versions")
def get_versions(name: str):
    records = get_registry().get_versions(name)
    return {"function_name": name, "versions": [r.model_dump() for r in records]}


@router.post("/v1/oma/function-types/{name}/code-location")
def set_code_location(name: str, req: CodeLocationRequest):
    location = get_registry().set_code_location(name, CodeLocation(**req.model_dump()))
    return location.model_dump()


@router.post("/v1/oma/function-types/{name}/record-usage")
def record_usage(name: str, req: RecordUsageRequest):
    record = get_registry().record_usage(name, req.used_in, req.used_in_kind)
    return record.model_dump()


@router.post("/v1/oma/function-types/{name}/record-version")
def record_version(name: str, req: RecordVersionRequest):
    record = get_registry().record_version(name, req.snapshot, req.recorded_by)
    return record.model_dump()
