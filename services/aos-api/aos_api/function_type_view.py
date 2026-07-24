"""W1-18 · OMA Function Type 视图。

Function 作为 Object Type 的管理视图：聚合 W1-7 FuncSpec + W1-19 PythonFunction，
提供概览 + 使用历史 + 版本历史 + 跳转代码库。

详见 docs/palantier/20_tech/220tech_oma-function-type.md。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


MAX_VERSIONS = 100


class CodeLocation(BaseModel):
    repo: str = ""
    path: str = ""
    line: int = 0
    url: str = ""


class UsageRecord(BaseModel):
    function_name: str
    used_in: str
    used_in_kind: Literal["action", "pipeline_node"] = "action"
    recorded_at: str = Field(default_factory=_now)


class VersionRecord(BaseModel):
    function_name: str
    version: int
    snapshot: dict[str, Any]
    recorded_at: str = Field(default_factory=_now)
    recorded_by: str = ""


class FunctionTypeView(BaseModel):
    name: str
    kind: Literal["expression", "python"]
    description: str = ""
    signature: str
    created_at: str
    updated_at: str
    usage_count: int = 0
    version_count: int = 0
    latest_code_location: CodeLocation | None = None


class FunctionTypeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class FunctionRegistry:
    def __init__(self) -> None:
        self._usage: dict[str, list[UsageRecord]] = {}
        self._versions: dict[str, list[VersionRecord]] = {}
        self._code_locations: dict[str, CodeLocation] = {}
        self._lock = threading.Lock()

    def aggregate_all(self) -> list[FunctionTypeView]:
        from .functions_python_builder import get_builder as get_python_builder
        from .shell_core import get_core

        views: list[FunctionTypeView] = []
        for func in get_core().list_funcs():
            views.append(self._view_from_func(func))
        for pf in get_python_builder().list_all():
            views.append(self._view_from_python(pf))
        return views

    def get_view(self, name: str) -> FunctionTypeView:
        from .functions_python_builder import get_builder as get_python_builder
        from .shell_core import get_core

        for func in get_core().list_funcs():
            if func.name == name:
                return self._view_from_func(func)
        for pf in get_python_builder().list_all():
            if pf.name == name:
                return self._view_from_python(pf)
        raise FunctionTypeError("NOT_FOUND", f"函数 {name!r} 不存在")

    def _view_from_func(self, func: Any) -> FunctionTypeView:
        name = func.name
        return FunctionTypeView(
            name=name,
            kind=func.kind,
            description=func.description,
            signature=f"f(params) -> {func.ref}",
            created_at=_now(),
            updated_at=_now(),
            usage_count=len(self._usage.get(name, [])),
            version_count=len(self._versions.get(name, [])),
            latest_code_location=self._code_locations.get(name),
        )

    def _view_from_python(self, pf: Any) -> FunctionTypeView:
        name = pf.name
        return FunctionTypeView(
            name=name,
            kind="python",
            description=pf.description,
            signature="transform(rows: list) -> list",
            created_at=pf.created_at,
            updated_at=pf.updated_at,
            usage_count=len(self._usage.get(name, [])),
            version_count=len(self._versions.get(name, [])),
            latest_code_location=self._code_locations.get(name),
        )

    def get_usage(self, name: str) -> list[UsageRecord]:
        return list(self._usage.get(name, []))

    def get_versions(self, name: str) -> list[VersionRecord]:
        return list(self._versions.get(name, []))

    def record_usage(self, name: str, used_in: str, used_in_kind: str = "action") -> UsageRecord:
        record = UsageRecord(function_name=name, used_in=used_in, used_in_kind=used_in_kind)
        with self._lock:
            self._usage.setdefault(name, []).append(record)
        return record

    def record_version(
        self, name: str, snapshot: dict[str, Any], recorded_by: str = ""
    ) -> VersionRecord:
        with self._lock:
            versions = self._versions.setdefault(name, [])
            version_num = len(versions) + 1
            record = VersionRecord(
                function_name=name,
                version=version_num,
                snapshot=snapshot,
                recorded_by=recorded_by,
            )
            versions.append(record)
            if len(versions) > MAX_VERSIONS:
                versions.pop(0)
            return record

    def set_code_location(self, name: str, location: CodeLocation) -> CodeLocation:
        with self._lock:
            self._code_locations[name] = location
            return location


_registry = FunctionRegistry()


def get_registry() -> FunctionRegistry:
    return _registry
