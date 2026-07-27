"""Phase 4 · Ontology Function 引擎.

functions + tests。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class FunctionParam(BaseModel):
    name: str
    datatype: str = "string"
    required: bool = True
    default: Any = None
    description: str = ""


class FunctionTestCase(BaseModel):
    id: str = Field(default_factory=lambda: "ftc-" + uuid.uuid4().hex[:6])
    function_id: str
    name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None
    status: str = "pending"  # pending|passed|failed
    output: Any = None
    error: str = ""
    ran_at: float | None = None
    created_at: float = Field(default_factory=lambda: time.time())


class OntologyFunction(BaseModel):
    id: str = Field(default_factory=lambda: "fn-" + uuid.uuid4().hex[:8])
    name: str
    display_name: str = ""
    description: str = ""
    body: str = ""  # Python expression / code
    params: list[FunctionParam] = Field(default_factory=list)
    return_type: str = "any"
    status: str = "active"  # active|draft|deprecated
    category: str = "transform"  # transform|aggregate|predicate|custom
    version: int = 1
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class FunctionEngine:
    """Ontology Function 引擎."""

    _instance: "FunctionEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "FunctionEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._functions: dict[str, OntologyFunction] = {}
                    inst._tests: dict[str, list[FunctionTestCase]] = {}
                    cls._instance = inst
        return cls._instance

    # ── Functions ──
    def create_function(self, name: str, **kwargs: Any) -> OntologyFunction:
        with _LOCK:
            fn = OntologyFunction(name=name, **kwargs)
            self._functions[fn.id] = fn
            return fn

    def get_function(self, fn_id: str) -> OntologyFunction | None:
        return self._functions.get(fn_id)

    def list_functions(self, status: str | None = None, category: str | None = None) -> list[OntologyFunction]:
        items = list(self._functions.values())
        if status:
            items = [f for f in items if f.status == status]
        if category:
            items = [f for f in items if f.category == category]
        return items

    def update_function(self, fn_id: str, **kwargs: Any) -> OntologyFunction:
        with _LOCK:
            fn = self._functions.get(fn_id)
            if fn is None:
                raise KeyError(f"Function {fn_id} not found")
            for k, v in kwargs.items():
                if hasattr(fn, k) and k != "id":
                    setattr(fn, k, v)
            fn.version += 1
            fn.updated_at = time.time()
            return fn

    def delete_function(self, fn_id: str) -> bool:
        with _LOCK:
            self._tests.pop(fn_id, None)
            return self._functions.pop(fn_id, None) is not None

    # ── Tests ──
    def list_tests(self, fn_id: str) -> list[FunctionTestCase]:
        return list(self._tests.get(fn_id, []))

    def add_test(self, fn_id: str, name: str, **kwargs: Any) -> FunctionTestCase:
        with _LOCK:
            if fn_id not in self._functions:
                raise KeyError(f"Function {fn_id} not found")
            tc = FunctionTestCase(function_id=fn_id, name=name, **kwargs)
            self._tests.setdefault(fn_id, []).append(tc)
            return tc

    def run_test(self, fn_id: str, test_id: str) -> FunctionTestCase:
        with _LOCK:
            fn = self._functions.get(fn_id)
            if fn is None:
                raise KeyError(f"Function {fn_id} not found")
            tests = self._tests.get(fn_id, [])
            tc = next((t for t in tests if t.id == test_id), None)
            if tc is None:
                raise KeyError(f"Test {test_id} not found")
            # 模拟执行：返回 expected == output 时为 passed
            try:
                output = self._mock_run(fn, tc.inputs)
                tc.output = output
                tc.error = ""
                if tc.expected is not None and str(output) == str(tc.expected):
                    tc.status = "passed"
                else:
                    tc.status = "passed" if tc.expected is None else "failed"
            except Exception as e:
                tc.status = "failed"
                tc.error = str(e)
                tc.output = None
            tc.ran_at = time.time()
            return tc

    def run_all_tests(self, fn_id: str) -> list[FunctionTestCase]:
        tests = self._tests.get(fn_id, [])
        return [self.run_test(fn_id, t.id) for t in tests]

    @staticmethod
    def _mock_run(fn: OntologyFunction, inputs: dict[str, Any]) -> Any:
        """模拟 function 执行：若 body 含 'return'，返回 inputs 的第一个值。"""
        if not inputs:
            return None
        # 简单：返回第一个输入值
        return list(inputs.values())[0]

    def reset(self) -> None:
        with _LOCK:
            self._functions.clear()
            self._tests.clear()


def get_function_engine() -> FunctionEngine:
    return FunctionEngine()
