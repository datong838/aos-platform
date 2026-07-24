"""W2-#18 · 工具集注册（Capability 深度集成）。

ToolDef / ToolRegistry / Capability / CapabilityStore。
Logic 编排通过 use_tool Block 调用注册的工具，结果写回变量。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.2。
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field


ToolHandler = Callable[[dict[str, Any]], Any]


class ToolDef(BaseModel):
    id: str = Field(default_factory=lambda: "tool-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ToolRegistry:
    """工具注册表：注册 handler、列出元信息、调用执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, tool: ToolDef, handler: ToolHandler) -> ToolDef:
        if not tool.name:
            raise ToolError("MISSING_NAME", "工具缺少 name")
        self._tools[tool.id] = tool
        self._handlers[tool.id] = handler
        return tool

    def register_simple(
        self, name: str, handler: ToolHandler, description: str = ""
    ) -> ToolDef:
        tool = ToolDef(name=name, description=description)
        return self.register(tool, handler)

    def get(self, tool_id: str) -> ToolDef | None:
        return self._tools.get(tool_id)

    def find_by_name(self, name: str) -> ToolDef | None:
        for tool in self._tools.values():
            if tool.name == name:
                return tool
        return None

    def list_all(self) -> list[ToolDef]:
        return list(self._tools.values())

    def invoke(self, tool_id: str, args: dict[str, Any] | None = None) -> Any:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolError("UNKNOWN_TOOL", f"未知工具 {tool_id!r}")
        handler = self._handlers[tool_id]
        try:
            return handler(args or {})
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("TOOL_FAILED", f"工具 {tool.name} 执行失败：{exc}") from exc

    def remove(self, tool_id: str) -> bool:
        existed = tool_id in self._tools
        self._tools.pop(tool_id, None)
        self._handlers.pop(tool_id, None)
        return existed


class Capability(BaseModel):
    id: str = Field(default_factory=lambda: "cap-" + uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    tool_ids: list[str] = Field(default_factory=list)


class CapabilityStore:
    """能力分组：把多个工具聚合成一个 Capability，供前端展示/权限分配。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._caps: dict[str, Capability] = {}

    def define(self, cap: Capability) -> Capability:
        if not cap.name:
            raise ToolError("MISSING_NAME", "能力缺少 name")
        self._caps[cap.id] = cap
        return cap

    def get(self, cap_id: str) -> Capability | None:
        return self._caps.get(cap_id)

    def list_all(self) -> list[Capability]:
        return list(self._caps.values())

    def add_tool(self, cap_id: str, tool_id: str) -> Capability:
        cap = self._caps.get(cap_id)
        if cap is None:
            raise ToolError("UNKNOWN_CAPABILITY", f"未知能力 {cap_id!r}")
        if self._registry.get(tool_id) is None:
            raise ToolError("UNKNOWN_TOOL", f"工具 {tool_id!r} 未注册")
        if tool_id not in cap.tool_ids:
            cap.tool_ids.append(tool_id)
        return cap

    def remove_tool(self, cap_id: str, tool_id: str) -> Capability:
        cap = self._caps.get(cap_id)
        if cap is None:
            raise ToolError("UNKNOWN_CAPABILITY", f"未知能力 {cap_id!r}")
        if tool_id in cap.tool_ids:
            cap.tool_ids.remove(tool_id)
        return cap

    def tools_of(self, cap_id: str) -> list[ToolDef]:
        cap = self._caps.get(cap_id)
        if cap is None:
            return []
        return [t for tid in cap.tool_ids if (t := self._registry.get(tid)) is not None]

    def delete(self, cap_id: str) -> bool:
        existed = cap_id in self._caps
        self._caps.pop(cap_id, None)
        return existed


_registry = ToolRegistry()
_capability_store: CapabilityStore | None = None


def get_registry() -> ToolRegistry:
    return _registry


def get_capability_store() -> CapabilityStore:
    global _capability_store
    if _capability_store is None:
        _capability_store = CapabilityStore(_registry)
    return _capability_store
