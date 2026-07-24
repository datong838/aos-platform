"""W1-7 · 壳核模式（Shell-Core Pattern）。

ACT-SPEC（壳：Action 声明性规格）+ FUNC-SPEC（核：函数实现引用）+ ShellCore 编排器。
壳负责协议（参数校验 + 写回），核负责计算（W1-1 表达式 或 W1-19 Python）。

详见 docs/palantier/20_tech/220tech_shell-core.md。
"""
from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from .function_engine import FunctionError, evaluate, parse
from .functions_python_builder import PythonBuilderError, get_builder as get_python_builder
from .writeback import WritebackError, WritebackOp, get_store as get_writeback_store


_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "boolean": (bool,),
    "list": (list,),
    "object": (dict,),
}


class FuncSpec(BaseModel):
    name: str
    kind: Literal["expression", "python"] = "expression"
    ref: str
    description: str = ""


class WritebackTarget(BaseModel):
    dataset_rid: str
    pk_field: str = "id"
    op: Literal["upsert", "soft_delete"] = "upsert"
    row_from: Literal["result", "params"] = "result"


class ActSpec(BaseModel):
    name: str
    func_ref: str
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_mapping: dict[str, str] = Field(default_factory=dict)
    writeback: WritebackTarget | None = None
    description: str = ""


class ShellExecution(BaseModel):
    action: str
    func_result: Any
    mapped: dict[str, Any]
    writeback_txn: str | None = None
    writeback_error: str | None = None
    duration_ms: float


class ShellCoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ShellCore:
    def __init__(self) -> None:
        self._funcs: dict[str, FuncSpec] = {}
        self._actions: dict[str, ActSpec] = {}

    def register_func(self, spec: FuncSpec) -> FuncSpec:
        self._funcs[spec.name] = spec
        return spec

    def register_action(self, spec: ActSpec) -> ActSpec:
        if spec.func_ref not in self._funcs:
            raise ShellCoreError("FUNC_NOT_FOUND", f"ActSpec 引用的 func {spec.func_ref!r} 未注册")
        self._actions[spec.name] = spec
        return spec

    def get_func(self, name: str) -> FuncSpec:
        if name not in self._funcs:
            raise ShellCoreError("FUNC_NOT_FOUND", f"FuncSpec {name!r} 不存在")
        return self._funcs[name]

    def get_action(self, name: str) -> ActSpec:
        if name not in self._actions:
            raise ShellCoreError("ACT_NOT_FOUND", f"ActSpec {name!r} 不存在")
        return self._actions[name]

    def list_funcs(self) -> list[FuncSpec]:
        return list(self._funcs.values())

    def list_actions(self) -> list[ActSpec]:
        return list(self._actions.values())

    def execute(self, action_name: str, params: dict[str, Any]) -> ShellExecution:
        start = time.perf_counter()
        act = self.get_action(action_name)
        self._validate_inputs(act, params)
        func = self.get_func(act.func_ref)
        result = self._run_core(func, params)
        mapped = self._apply_mapping(act, result, params)
        txn_id, wb_error = self._maybe_writeback(act, mapped, params)
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ShellExecution(
            action=action_name,
            func_result=result,
            mapped=mapped,
            writeback_txn=txn_id,
            writeback_error=wb_error,
            duration_ms=round(duration_ms, 2),
        )

    def _validate_inputs(self, act: ActSpec, params: dict[str, Any]) -> None:
        for field, type_name in act.input_schema.items():
            if field not in params:
                raise ShellCoreError("INPUT_MISSING", f"缺少必填参数 {field!r}")
            accepted = _TYPE_MAP.get(type_name)
            if accepted is None:
                raise ShellCoreError("BAD_SCHEMA", f"未知类型 {type_name!r}")
            if type_name == "number" and isinstance(params[field], bool):
                raise ShellCoreError("INPUT_TYPE_MISMATCH", f"参数 {field!r} 期望 number，实际 boolean")
            if not isinstance(params[field], accepted):
                raise ShellCoreError(
                    "INPUT_TYPE_MISMATCH",
                    f"参数 {field!r} 期望 {type_name}，实际 {type(params[field]).__name__}",
                )

    def _run_core(self, func: FuncSpec, params: dict[str, Any]) -> Any:
        try:
            if func.kind == "expression":
                expr = parse(func.ref)
                return evaluate(expr, params)
            if func.kind == "python":
                rows = get_python_builder().call_raw(func.ref, [params])
                return rows[0] if rows else None
            raise ShellCoreError("BAD_FUNC_KIND", f"未知 func kind {func.kind!r}")
        except FunctionError as exc:
            raise ShellCoreError("FUNC_EXEC_ERROR", f"表达式执行失败: {exc.message}") from exc
        except PythonBuilderError as exc:
            raise ShellCoreError("FUNC_EXEC_ERROR", f"Python 函数执行失败: {exc.message}") from exc

    def _apply_mapping(self, act: ActSpec, result: Any, params: dict[str, Any]) -> dict[str, Any]:
        if not act.output_mapping:
            return {"result": result}
        ctx = {"result": result, "params": params}
        mapped: dict[str, Any] = {}
        for field, expr_text in act.output_mapping.items():
            try:
                expr = parse(expr_text)
                mapped[field] = evaluate(expr, ctx)
            except FunctionError as exc:
                raise ShellCoreError("MAPPING_ERROR", f"输出映射 {field!r} 失败: {exc.message}") from exc
        return mapped

    def _maybe_writeback(
        self, act: ActSpec, mapped: dict[str, Any], params: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        if act.writeback is None:
            return None, None
        target = act.writeback
        row_src = mapped if target.row_from == "result" else params
        pk_value = row_src.get(target.pk_field) or params.get(target.pk_field)
        if pk_value is None:
            return None, f"missing pk field {target.pk_field!r}"
        try:
            store = get_writeback_store()
            txn_id = store.begin(target.dataset_rid)
            store.apply(txn_id, [WritebackOp(
                op=target.op, pk=str(pk_value), row=dict(row_src)
            )])
            store.commit(txn_id)
            return txn_id, None
        except WritebackError as exc:
            return None, f"{exc.code}: {exc.message}"


_core = ShellCore()


def get_core() -> ShellCore:
    return _core
