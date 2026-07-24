"""W1-19 · Functions Python Builder API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.functions_python_builder import PythonBuilderError, get_builder

router = APIRouter(tags=["python-functions"])


class RegisterRequest(BaseModel):
    name: str
    code: str
    description: str = ""


class ExecuteRequest(BaseModel):
    rows: list[dict[str, Any]]


class ValidateRequest(BaseModel):
    code: str


def _map_error(err: PythonBuilderError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/python-functions")
def register_function(req: RegisterRequest):
    try:
        pf = get_builder().register(req.name, req.code, req.description)
    except PythonBuilderError as err:
        raise _map_error(err) from err
    return pf.model_dump()


@router.get("/v1/python-functions")
def list_functions():
    return {"functions": [pf.model_dump() for pf in get_builder().list_all()]}


@router.get("/v1/python-functions/{name}")
def get_function(name: str):
    try:
        return get_builder().get(name).model_dump()
    except PythonBuilderError as err:
        raise _map_error(err, 404) from err


@router.post("/v1/python-functions/{name}/execute")
def execute_function(name: str, req: ExecuteRequest):
    try:
        result = get_builder().execute(name, req.rows)
    except PythonBuilderError as err:
        raise _map_error(err) from err
    return result.model_dump()


@router.post("/v1/python-functions/validate")
def validate_function(req: ValidateRequest):
    errors = get_builder().validate_code(req.code)
    return {"errors": errors, "ok": len(errors) == 0}


@router.delete("/v1/python-functions/{name}")
def delete_function(name: str):
    try:
        get_builder().delete(name)
    except PythonBuilderError as err:
        raise _map_error(err, 404) from err
    return {"deleted": name}
