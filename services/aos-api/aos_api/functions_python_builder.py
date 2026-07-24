"""W1-19 · Functions Python Builder。

用户提交 Python 代码（必须定义 `transform(rows)`），在受限 namespace 中执行，
作为 Pipeline Builder 的自定义 transform 函数。

安全防护：ast 静态扫描（黑名单 import + 危险内建 + dunder）+ namespace 限制 +
SIGALRM 软超时（主线程）+ 行数/AST 节点数上限。

详见 docs/palantier/20_tech/220tech_functions-python-builder.md。
"""
from __future__ import annotations

import ast
import re
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


MAX_CODE_SIZE = 5_000
MAX_AST_NODES = 1_000
MAX_ROWS = 10_000
DEFAULT_TIMEOUT = 5.0

_BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pickle",
    "ctypes", "multiprocessing", "pty", "platform", "importlib",
}
_BLOCKED_BUILTINS = {
    "eval", "exec", "compile", "__import__", "globals", "locals",
    "vars", "open", "input", "breakpoint", "memoryview",
}
_SAFE_BUILTINS: dict[str, Any] = {
    "len": len, "sum": sum, "min": min, "max": max,
    "sorted": sorted, "reversed": reversed, "filter": filter, "map": map,
    "range": range, "abs": abs, "round": round, "any": any, "all": all,
    "zip": zip, "enumerate": enumerate, "divmod": divmod, "pow": pow,
    "dict": dict, "list": list, "tuple": tuple, "set": set, "frozenset": frozenset,
    "str": str, "int": int, "float": float, "bool": bool, "bytes": bytes,
    "True": True, "False": False, "None": None,
    "isinstance": isinstance, "type": type, "hasattr": hasattr, "getattr": getattr,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError, "StopIteration": StopIteration,
}

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class PythonFunction(BaseModel):
    name: str
    code: str
    description: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ExecutionResult(BaseModel):
    name: str
    input_count: int
    output_count: int
    duration_ms: float
    rows: list[dict[str, Any]]


class PythonBuilderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class _TimeoutError(Exception):
    pass


def _check_code(code: str) -> list[str]:
    errors: list[str] = []
    if len(code) > MAX_CODE_SIZE:
        errors.append(f"CODE_TOO_LARGE: 代码 {len(code)} 字节超过上限 {MAX_CODE_SIZE}")
        return errors
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        errors.append(f"CODE_PARSE_ERROR: 语法错误 line {exc.lineno}: {exc.msg}")
        return errors
    node_count = 0
    for node in ast.walk(tree):
        node_count += 1
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_MODULES:
                    errors.append(f"CODE_BLOCKED_IMPORT: 禁止 import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in _BLOCKED_MODULES:
                    errors.append(f"CODE_BLOCKED_IMPORT: 禁止 from {node.module} import")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _BLOCKED_BUILTINS:
                errors.append(f"CODE_BLOCKED_BUILTIN: 禁止调用 {fn.id}()")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                if not isinstance(node.value, ast.Name) or node.value.id not in {"self"}:
                    errors.append(f"CODE_BLOCKED_DUNDER: 禁止访问 {node.attr}")
    if node_count > MAX_AST_NODES:
        errors.append(f"CODE_TOO_COMPLEX: AST 节点 {node_count} 超过上限 {MAX_AST_NODES}")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "transform" for n in ast.walk(tree)):
        errors.append("CODE_NO_TRANSFORM: 必须定义 def transform(rows): ...")
    return errors


def _build_namespace(code: str) -> dict[str, Any]:
    ns: dict[str, Any] = {"__builtins__": dict(_SAFE_BUILTINS), "__name__": "__python_builder__"}
    try:
        exec(compile(code, "<python-builder>", "exec"), ns)
    except Exception as exc:
        raise PythonBuilderError("CODE_RUNTIME_ERROR", f"编译/执行失败: {exc}") from exc
    return ns


def _extract_transform(ns: dict[str, Any]) -> Callable[[list], list]:
    fn = ns.get("transform")
    if not callable(fn):
        raise PythonBuilderError("CODE_NO_TRANSFORM", "namespace 中无 transform 可调用对象")
    return fn


class PythonBuilder:
    def __init__(self) -> None:
        self._functions: dict[str, PythonFunction] = {}
        self._lock = threading.Lock()

    def register(self, name: str, code: str, description: str = "") -> PythonFunction:
        if not _NAME_RE.match(name):
            raise PythonBuilderError("BAD_NAME", f"函数名 {name!r} 不合法（需匹配 {_NAME_RE.pattern}）")
        errors = _check_code(code)
        if errors:
            raise PythonBuilderError(errors[0].split(":")[0], "; ".join(errors))
        with self._lock:
            existing = self._functions.get(name)
            now = _now()
            if existing is None:
                pf = PythonFunction(name=name, code=code, description=description, created_at=now, updated_at=now)
            else:
                pf = existing.model_copy(update={"code": code, "description": description, "updated_at": now})
            self._functions[name] = pf
            return pf

    def get(self, name: str) -> PythonFunction:
        if name not in self._functions:
            raise PythonBuilderError("NOT_FOUND", f"函数 {name!r} 不存在")
        return self._functions[name]

    def list_all(self) -> list[PythonFunction]:
        return list(self._functions.values())

    def delete(self, name: str) -> None:
        with self._lock:
            if name not in self._functions:
                raise PythonBuilderError("NOT_FOUND", f"函数 {name!r} 不存在")
            del self._functions[name]

    def validate_code(self, code: str) -> list[str]:
        return _check_code(code)

    def call_raw(self, name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pf = self.get(name)
        return self._run(pf.code, rows, DEFAULT_TIMEOUT)

    def execute(self, name: str, rows: list[dict[str, Any]], timeout: float = DEFAULT_TIMEOUT) -> ExecutionResult:
        pf = self.get(name)
        if len(rows) > MAX_ROWS:
            raise PythonBuilderError("INPUT_TOO_LARGE", f"输入行数 {len(rows)} 超过上限 {MAX_ROWS}")
        start = time.perf_counter()
        result = self._run(pf.code, rows, timeout)
        duration_ms = (time.perf_counter() - start) * 1000.0
        truncated = result[:MAX_ROWS]
        return ExecutionResult(
            name=name,
            input_count=len(rows),
            output_count=len(result),
            duration_ms=round(duration_ms, 2),
            rows=truncated,
        )

    def _run(self, code: str, rows: list[dict[str, Any]], timeout: float) -> list[dict[str, Any]]:
        ns = _build_namespace(code)
        fn = _extract_transform(ns)
        result = self._invoke(fn, rows, timeout)
        if not isinstance(result, list):
            raise PythonBuilderError("CODE_BAD_RETURN", f"transform 必须返回 list，实际 {type(result).__name__}")
        return result

    def _invoke(self, fn: Callable[[list], list], rows: list, timeout: float) -> list:
        if threading.current_thread() is threading.main_thread():
            return self._invoke_with_alarm(fn, rows, timeout)
        return fn(rows)

    def _invoke_with_alarm(self, fn: Callable[[list], list], rows: list, timeout: float) -> list:
        def _handler(signum, frame):
            raise _TimeoutError("transform 执行超时")

        old = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            return fn(rows)
        except _TimeoutError as exc:
            raise PythonBuilderError("TIMEOUT", str(exc)) from exc
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


_builder = PythonBuilder()


def get_builder() -> PythonBuilder:
    return _builder
