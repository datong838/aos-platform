"""W2-#18 legacy in-memory Tool functions, no public HTTP registration.

Formal Tool HTTP issuance requires a signed source and dedicated issuer.
The W2-B Python ToolRegistry/Logic interface remains available internally.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError, is_not_found_code
from aos_api.tool_registry import (
    Capability,
    CapabilityStore,
    ToolDef,
    ToolError,
    ToolHandler,
    ToolRegistry,
    get_capability_store,
    get_registry,
)

router = APIRouter(tags=["tool-registry"])


def _map_error(err: ToolError) -> ApiError:
    # NOTE(not-found-status)：not-found 语义必须映射为 404（平台约定：
    # 线上实测「NOT_FOUND 类码」为 404×537 / 400×7，那 7 处是映射缺陷）。
    # 共享判据只对 NOT_FOUND / *_NOT_FOUND 生效，其余码的状态码行为完全不变。
    status = 404 if is_not_found_code(err.code) else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class RegisterToolRequest(BaseModel):
    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    code: str  # 定义 handler(args: dict) -> Any


class InvokeToolRequest(BaseModel):
    tool_id: str
    args: dict[str, Any] = Field(default_factory=dict)


class DefineCapabilityRequest(BaseModel):
    name: str
    description: str = ""
    tool_ids: list[str] = Field(default_factory=list)


class AddToolToCapabilityRequest(BaseModel):
    tool_id: str


def _compile_handler(code: str) -> ToolHandler:
    sandbox: dict[str, Any] = {"__builtins__": {}}
    try:
        exec(code, sandbox)
    except Exception as err:
        raise ApiError(code="TOOL_CODE_INVALID", message=f"工具代码解析失败：{err}", status_code=400) from err
    fn = sandbox.get("handler")
    if not callable(fn):
        raise ApiError(code="TOOL_CODE_INVALID", message="代码需定义 handler(args) 函数", status_code=400)
    return fn


def list_tools():
    reg = get_registry()
    return {"items": [t.model_dump() for t in reg.list_all()]}


def register_tool(req: RegisterToolRequest):
    reg = get_registry()
    handler = _compile_handler(req.code)
    tool = ToolDef(name=req.name, description=req.description, parameters_schema=req.parameters_schema)
    try:
        reg.register(tool, handler)
    except ToolError as err:
        raise _map_error(err) from err
    return tool.model_dump()


def get_tool(tool_id: str):
    reg = get_registry()
    tool = reg.get(tool_id)
    if tool is None:
        raise ApiError(code="UNKNOWN_TOOL", message=f"未知工具 {tool_id}", status_code=404)
    return tool.model_dump()


def invoke_tool(req: InvokeToolRequest):
    reg = get_registry()
    try:
        result = reg.invoke(req.tool_id, req.args)
    except ToolError as err:
        raise _map_error(err) from err
    return {"tool_id": req.tool_id, "result": result}


def delete_tool(tool_id: str):
    reg = get_registry()
    ok = reg.remove(tool_id)
    return {"tool_id": tool_id, "deleted": ok}


def list_capabilities():
    store = get_capability_store()
    return {"items": [c.model_dump() for c in store.list_all()]}


def define_capability(req: DefineCapabilityRequest):
    store = get_capability_store()
    cap = Capability(name=req.name, description=req.description, tool_ids=req.tool_ids)
    try:
        store.define(cap)
    except ToolError as err:
        raise _map_error(err) from err
    return cap.model_dump()


def add_tool_to_capability(cap_id: str, req: AddToolToCapabilityRequest):
    store = get_capability_store()
    try:
        cap = store.add_tool(cap_id, req.tool_id)
    except ToolError as err:
        raise _map_error(err) from err
    return cap.model_dump()


def list_capability_tools(cap_id: str):
    store = get_capability_store()
    return {"items": [t.model_dump() for t in store.tools_of(cap_id)]}
