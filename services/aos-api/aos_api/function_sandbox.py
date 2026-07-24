"""W1-10 · Function 沙箱 + 类型安全 + 可组合。

沙箱求值（超时+递归深度+AST 节点数限制）、Function 可组合链式调用、TypeScript 类型生成。
基于 W1-1 function_engine.py 扩展。

详见 docs/palantier/20_tech/220tech_function-sandbox.md。
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from aos_api.function_engine import (
    Evaluator,
    FunctionError,
    TypeInferer,
    evaluate,
    parse,
)


# --------------------------------------------------------------------------- #
# 沙箱求值
# --------------------------------------------------------------------------- #
class SandboxError(FunctionError):
    pass


class SandboxedEvaluator:
    MAX_NODES = 1000
    MAX_DEPTH = 50
    TIMEOUT_SEC = 5.0

    def eval(self, text: str, context: dict[str, Any] | None = None) -> Any:
        context = context or {}
        expr = parse(text)
        self._count_nodes(expr)
        result_box: dict[str, Any] = {}
        exc_box: list[BaseException] = []

        def _run() -> None:
            try:
                ev = Evaluator()
                result_box["value"] = ev.eval(expr, context)
            except BaseException as e:
                exc_box.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(self.TIMEOUT_SEC)
        if t.is_alive():
            raise SandboxError("TIMEOUT", f"表达式执行超过 {self.TIMEOUT_SEC}s 超时")
        if exc_box:
            raise exc_box[0]
        return result_box.get("value")

    def _count_nodes(self, expr: Any, depth: int = 0) -> int:
        if depth > self.MAX_DEPTH:
            raise SandboxError("DEPTH_EXCEEDED", f"AST 深度超过 {self.MAX_DEPTH}")
        count = 1
        children: list[Any] = []
        if hasattr(expr, "obj"):
            children.append(expr.obj)
        if hasattr(expr, "args"):
            children.extend(expr.args)
        if hasattr(expr, "left"):
            children.append(expr.left)
        if hasattr(expr, "right"):
            children.append(expr.right)
        if hasattr(expr, "operand"):
            children.append(expr.operand)
        if hasattr(expr, "cond"):
            children.extend([expr.cond, expr.then, getattr(expr, "else_", None)])
        for child in children:
            if child is not None:
                count += self._count_nodes(child, depth + 1)
        if count > self.MAX_NODES:
            raise SandboxError("NODE_LIMIT", f"AST 节点数超过 {self.MAX_NODES}")
        return count


# --------------------------------------------------------------------------- #
# 可组合 Function
# --------------------------------------------------------------------------- #
class FunctionDef:
    def __init__(self, name: str, expression: str, params: dict[str, str] | None = None) -> None:
        self.name = name
        self.expression = expression
        self.params = params or {}


class CircularDependencyError(FunctionError):
    pass


class FunctionComposer:
    def __init__(self) -> None:
        self._registry: dict[str, FunctionDef] = {}

    def register(self, defs: list[FunctionDef]) -> None:
        for d in defs:
            self._registry[d.name] = d

    def call(self, entry: str, context: dict[str, Any] | None = None) -> Any:
        if entry not in self._registry:
            raise FunctionError("UNDEFINED_FUNCTION", f"未注册的函数 {entry!r}")
        context = context or {}
        ev = Evaluator()
        visiting: set[str] = set()
        for name in self._registry:
            ev.register_function(name, self._make_wrapper(name, context, visiting, ev))
        visiting.add(entry)
        fn = self._registry[entry]
        expr = parse(fn.expression)
        return ev.eval(expr, context)

    def _make_wrapper(
        self,
        name: str,
        context: dict[str, Any],
        visiting: set[str],
        ev: Evaluator,
    ) -> Callable[[list[Any], Evaluator], Any]:
        registry = self._registry

        def fn(args: list[Any], _ev: Evaluator) -> Any:
            if name in visiting:
                raise CircularDependencyError("CIRCULAR_DEPENDENCY", f"检测到循环依赖：{name}")
            visiting.add(name)
            fdef = registry[name]
            inner_expr = parse(fdef.expression)
            try:
                return ev.eval(inner_expr, context)
            finally:
                visiting.discard(name)

        return fn


# --------------------------------------------------------------------------- #
# TypeScript 类型生成
# --------------------------------------------------------------------------- #
_TS_MAP: dict[str, str] = {
    "number": "number",
    "string": "string",
    "boolean": "boolean",
    "null": "null",
    "any": "any",
    "object": "Record<string, any>",
    "array": "any[]",
}


class TypeGenerator:
    def generate(self, text: str, context_schema: dict[str, str] | None = None) -> str:
        expr = parse(text)
        inferer = TypeInferer(context_schema or {})
        inferred = inferer.infer(expr)
        return _TS_MAP.get(inferred, "any")

    def generate_interface(
        self, name: str, fields: dict[str, str]
    ) -> str:
        lines = [f"interface {name} {{"]
        for field, ftype in fields.items():
            lines.append(f"  {field}: {_TS_MAP.get(ftype, 'any')};")
        lines.append("}")
        return "\n".join(lines)
