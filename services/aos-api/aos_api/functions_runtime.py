"""W2-#26 · Functions 运行时。

统一 Function 注册表，支持 Python（真实沙箱）/TS（类型生成+元信息）/SQL。
- OntologyApi：函数运行时只读访问对象类型定义
- Workshop 绑定：函数可绑定到 Workshop 模块
- TS 函数：注册元信息 + 类型生成（无真实 TS 运行时，invoke 返回类型签名）

LLM 相关经 gateway 路由，不写死模型。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.5。
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from .multi_language_transform import LanguageKind


RuntimeLanguage = Literal["python", "typescript", "sql"]


class FunctionsRuntimeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class RuntimeFunction(BaseModel):
    id: str = Field(default_factory=lambda: "fn-" + uuid.uuid4().hex[:8])
    name: str
    language: RuntimeLanguage
    source: str
    description: str = ""
    params_schema: dict[str, str] = Field(default_factory=dict)
    return_type: str = "any"
    ontology_refs: list[str] = Field(default_factory=list)
    workshop_binding: str | None = None


class OntologyApi:
    """函数运行时可调用的只读 Ontology 接口（复用 W2-3 OntologyOutputStore）。"""

    def __init__(self, store: Any | None = None) -> None:
        if store is None:
            from .ontology_output import get_store
            store = get_store()
        self._store = store

    def list_object_types(self) -> list[dict[str, Any]]:
        return [otd.model_dump() for otd in self._store.list_all()]

    def get_object_type(self, otd_id: str) -> dict[str, Any] | None:
        otd = self._store.get(otd_id)
        return otd.model_dump() if otd else None

    def preview_objects(
        self, otd_id: str, rows: list[dict[str, Any]], limit: int = 100
    ) -> list[dict[str, Any]]:
        return self._store.preview_objects(otd_id, rows, limit)


def _generate_ts_signature(fn: RuntimeFunction) -> str:
    params = ", ".join(f"{k}: {v}" for k, v in fn.params_schema.items()) or "rows: any[]"
    return f"function {fn.name}({params}): {fn.return_type};"


class FunctionsRuntime:
    """统一 Function 注册表 + 执行分发 + Workshop 绑定。"""

    def __init__(self, ontology_api: OntologyApi | None = None) -> None:
        self._functions: dict[str, RuntimeFunction] = {}
        self._ontology_api = ontology_api or OntologyApi()

    @property
    def ontology(self) -> OntologyApi:
        return self._ontology_api

    def register(self, fn: RuntimeFunction) -> RuntimeFunction:
        if not fn.name:
            raise FunctionsRuntimeError("MISSING_NAME", "Function 缺少 name")
        if fn.language not in ("python", "typescript", "sql"):
            raise FunctionsRuntimeError("UNSUPPORTED_LANGUAGE", f"不支持的语言 {fn.language!r}")
        if fn.language == "python":
            from .functions_python_builder import get_builder
            try:
                get_builder().register(fn.name, fn.source, fn.description)
            except Exception as exc:
                raise FunctionsRuntimeError("REGISTER_FAILED", str(exc)) from exc
        if fn.language == "sql":
            self._validate_sql_source(fn.source)
        self._functions[fn.id] = fn
        return fn

    @staticmethod
    def _validate_sql_source(source: str) -> None:
        from .multi_language_transform import _SELECT_RE
        if not _SELECT_RE.match(source):
            raise FunctionsRuntimeError("SQL_INVALID", "SQL 源必须是 SELECT ... FROM ... 语句")

    def get(self, fn_id: str) -> RuntimeFunction | None:
        return self._functions.get(fn_id)

    def find_by_name(self, name: str) -> RuntimeFunction | None:
        for fn in self._functions.values():
            if fn.name == name:
                return fn
        return None

    def list_all(self) -> list[RuntimeFunction]:
        return list(self._functions.values())

    def list_by_workshop(self, workshop_module: str) -> list[RuntimeFunction]:
        return [fn for fn in self._functions.values() if fn.workshop_binding == workshop_module]

    def delete(self, fn_id: str) -> bool:
        existed = fn_id in self._functions
        self._functions.pop(fn_id, None)
        return existed

    def bind_workshop(self, fn_id: str, workshop_module: str) -> RuntimeFunction:
        fn = self._functions.get(fn_id)
        if fn is None:
            raise FunctionsRuntimeError("NOT_FOUND", f"Function {fn_id!r} 不存在")
        if not workshop_module:
            raise FunctionsRuntimeError("MISSING_WORKSHOP", "workshop_module 不能为空")
        updated = fn.model_copy(update={"workshop_binding": workshop_module})
        self._functions[fn_id] = updated
        return updated

    def invoke(self, fn_id: str, payload: Any) -> Any:
        fn = self._functions.get(fn_id)
        if fn is None:
            raise FunctionsRuntimeError("NOT_FOUND", f"Function {fn_id!r} 不存在")
        if fn.language == "python":
            from .functions_python_builder import get_builder
            rows = payload if isinstance(payload, list) else [payload] if payload else []
            try:
                return get_builder().call_raw(fn.name, rows)
            except Exception as exc:
                raise FunctionsRuntimeError("EXEC_FAILED", str(exc)) from exc
        if fn.language == "sql":
            from .multi_language_transform import _run_sql
            rows = payload if isinstance(payload, list) else []
            try:
                return _run_sql(fn.source, rows)
            except Exception as exc:
                raise FunctionsRuntimeError("EXEC_FAILED", str(exc)) from exc
        if fn.language == "typescript":
            return {
                "language": "typescript",
                "signature": _generate_ts_signature(fn),
                "note": "TS 运行时未实现，仅返回类型签名",
            }
        raise FunctionsRuntimeError("NOT_IMPLEMENTED", f"语言 {fn.language!r} 不可执行")

    def typescript_signature(self, fn_id: str) -> str:
        fn = self._functions.get(fn_id)
        if fn is None:
            raise FunctionsRuntimeError("NOT_FOUND", f"Function {fn_id!r} 不存在")
        return _generate_ts_signature(fn)


_runtime = FunctionsRuntime()


def get_runtime() -> FunctionsRuntime:
    return _runtime
