"""W2-#18 · 工具集注册 API 路由。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.2。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
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
    return ApiError(code=err.code, message=err.message, status_code=400)


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


@router.get("/v1/tools")
def list_tools():
    reg = get_registry()
    return {"items": [t.model_dump() for t in reg.list_all()]}


@router.post("/v1/tools/register")
def register_tool(req: RegisterToolRequest):
    reg = get_registry()
    handler = _compile_handler(req.code)
    tool = ToolDef(name=req.name, description=req.description, parameters_schema=req.parameters_schema)
    try:
        reg.register(tool, handler)
    except ToolError as err:
        raise _map_error(err) from err
    return tool.model_dump()


@router.get("/v1/tools/{tool_id}")
def get_tool(tool_id: str):
    reg = get_registry()
    tool = reg.get(tool_id)
    if tool is None:
        raise ApiError(code="UNKNOWN_TOOL", message=f"未知工具 {tool_id}", status_code=404)
    return tool.model_dump()


@router.post("/v1/tools/invoke")
def invoke_tool(req: InvokeToolRequest):
    reg = get_registry()
    try:
        result = reg.invoke(req.tool_id, req.args)
    except ToolError as err:
        raise _map_error(err) from err
    return {"tool_id": req.tool_id, "result": result}


@router.delete("/v1/tools/{tool_id}")
def delete_tool(tool_id: str):
    reg = get_registry()
    ok = reg.remove(tool_id)
    return {"tool_id": tool_id, "deleted": ok}


@router.get("/v1/capabilities")
def list_capabilities():
    store = get_capability_store()
    return {"items": [c.model_dump() for c in store.list_all()]}


@router.post("/v1/capabilities")
def define_capability(req: DefineCapabilityRequest):
    store = get_capability_store()
    cap = Capability(name=req.name, description=req.description, tool_ids=req.tool_ids)
    try:
        store.define(cap)
    except ToolError as err:
        raise _map_error(err) from err
    return cap.model_dump()


@router.post("/v1/capabilities/{cap_id}/tools")
def add_tool_to_capability(cap_id: str, req: AddToolToCapabilityRequest):
    store = get_capability_store()
    try:
        cap = store.add_tool(cap_id, req.tool_id)
    except ToolError as err:
        raise _map_error(err) from err
    return cap.model_dump()


@router.get("/v1/capabilities/{cap_id}/tools")
def list_capability_tools(cap_id: str):
    store = get_capability_store()
    return {"items": [t.model_dump() for t in store.tools_of(cap_id)]}
