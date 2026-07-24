"""W1-7 · 壳核模式 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.shell_core import ActSpec, FuncSpec, ShellCoreError, get_core

router = APIRouter(tags=["shell-core"])


class ExecuteRequest(BaseModel):
    params: dict[str, Any]


def _map_error(err: ShellCoreError, status: int = 400) -> ApiError:
    if err.code in {"ACT_NOT_FOUND", "FUNC_NOT_FOUND"}:
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/shell-core/funcs")
def register_func(spec: FuncSpec):
    try:
        return get_core().register_func(spec).model_dump()
    except ShellCoreError as err:
        raise _map_error(err) from err


@router.get("/v1/shell-core/funcs")
def list_funcs():
    return {"funcs": [f.model_dump() for f in get_core().list_funcs()]}


@router.get("/v1/shell-core/funcs/{name}")
def get_func(name: str):
    try:
        return get_core().get_func(name).model_dump()
    except ShellCoreError as err:
        raise _map_error(err) from err


@router.post("/v1/shell-core/actions")
def register_action(spec: ActSpec):
    try:
        return get_core().register_action(spec).model_dump()
    except ShellCoreError as err:
        raise _map_error(err) from err


@router.get("/v1/shell-core/actions")
def list_actions():
    return {"actions": [a.model_dump() for a in get_core().list_actions()]}


@router.get("/v1/shell-core/actions/{name}")
def get_action(name: str):
    try:
        return get_core().get_action(name).model_dump()
    except ShellCoreError as err:
        raise _map_error(err) from err


@router.post("/v1/shell-core/actions/{name}/execute")
def execute_action(name: str, req: ExecuteRequest):
    try:
        result = get_core().execute(name, req.params)
    except ShellCoreError as err:
        raise _map_error(err) from err
    return result.model_dump()
