"""W2-#26 · Functions 运行时测试。"""
from __future__ import annotations

import pytest

from aos_api.functions_runtime import (
    FunctionsRuntime,
    FunctionsRuntimeError,
    OntologyApi,
    RuntimeFunction,
)


@pytest.fixture
def runtime() -> FunctionsRuntime:
    return FunctionsRuntime()


def _py_source() -> str:
    return "def transform(rows):\n    return [{**r, 'squared': r.get('x', 0) ** 2} for r in rows]"


# ---------- 注册与基本查询 ----------


def test_register_python_function(runtime: FunctionsRuntime):
    fn = runtime.register(RuntimeFunction(name="square", language="python", source=_py_source()))
    assert fn.id in {f.id for f in runtime.list_all()}
    assert runtime.get(fn.id).name == "square"


def test_register_missing_name_raises(runtime: FunctionsRuntime):
    with pytest.raises(FunctionsRuntimeError) as exc:
        runtime.register(RuntimeFunction(name="", language="python", source="x"))
    assert exc.value.code == "MISSING_NAME"


def test_register_unsupported_language_raises(runtime: FunctionsRuntime):
    fn = RuntimeFunction.model_construct(name="j", language="java", source="x")
    with pytest.raises(FunctionsRuntimeError) as exc:
        runtime.register(fn)
    assert exc.value.code == "UNSUPPORTED_LANGUAGE"


def test_find_by_name(runtime: FunctionsRuntime):
    runtime.register(RuntimeFunction(name="finder", language="python", source=_py_source()))
    assert runtime.find_by_name("finder") is not None
    assert runtime.find_by_name("missing") is None


def test_delete_function(runtime: FunctionsRuntime):
    fn = runtime.register(RuntimeFunction(name="tmp", language="python", source=_py_source()))
    assert runtime.delete(fn.id) is True
    assert runtime.get(fn.id) is None
    assert runtime.delete(fn.id) is False


# ---------- 执行 ----------


def test_invoke_python_function(runtime: FunctionsRuntime):
    fn = runtime.register(RuntimeFunction(name="sq", language="python", source=_py_source()))
    result = runtime.invoke(fn.id, [{"x": 2}, {"x": 3}])
    assert result == [{"x": 2, "squared": 4}, {"x": 3, "squared": 9}]


def test_invoke_unknown_function_raises(runtime: FunctionsRuntime):
    with pytest.raises(FunctionsRuntimeError) as exc:
        runtime.invoke("ghost", [])
    assert exc.value.code == "NOT_FOUND"


def test_invoke_sql_function(runtime: FunctionsRuntime):
    fn = runtime.register(RuntimeFunction(name="q", language="sql", source="SELECT * FROM t WHERE v > 5"))
    result = runtime.invoke(fn.id, [{"v": 1}, {"v": 10}])
    assert result == [{"v": 10}]


def test_register_invalid_sql_raises(runtime: FunctionsRuntime):
    with pytest.raises(FunctionsRuntimeError) as exc:
        runtime.register(RuntimeFunction(name="bad", language="sql", source="DROP TABLE t"))
    assert exc.value.code == "SQL_INVALID"


def test_typescript_function_invoke_returns_signature(runtime: FunctionsRuntime):
    fn = runtime.register(
        RuntimeFunction(
            name="greet",
            language="typescript",
            source="function greet(name: string): string { return name; }",
            params_schema={"name": "string"},
            return_type="string",
        )
    )
    result = runtime.invoke(fn.id, None)
    assert result["language"] == "typescript"
    assert "greet" in result["signature"]


def test_typescript_signature_generation(runtime: FunctionsRuntime):
    fn = runtime.register(
        RuntimeFunction(
            name="calc",
            language="typescript",
            source="// stub",
            params_schema={"a": "number", "b": "number"},
            return_type="number",
        )
    )
    sig = runtime.typescript_signature(fn.id)
    assert "a: number" in sig and "b: number" in sig and "number" in sig


# ---------- Workshop 绑定 ----------


def test_bind_workshop(runtime: FunctionsRuntime):
    fn = runtime.register(RuntimeFunction(name="wfn", language="python", source=_py_source()))
    updated = runtime.bind_workshop(fn.id, "OrderDashboard")
    assert updated.workshop_binding == "OrderDashboard"
    assert runtime.list_by_workshop("OrderDashboard")[0].id == fn.id


def test_bind_workshop_unknown_function_raises(runtime: FunctionsRuntime):
    with pytest.raises(FunctionsRuntimeError) as exc:
        runtime.bind_workshop("ghost", "M")
    assert exc.value.code == "NOT_FOUND"


def test_bind_workshop_empty_module_raises(runtime: FunctionsRuntime):
    fn = runtime.register(RuntimeFunction(name="w2", language="python", source=_py_source()))
    with pytest.raises(FunctionsRuntimeError) as exc:
        runtime.bind_workshop(fn.id, "")
    assert exc.value.code == "MISSING_WORKSHOP"


# ---------- OntologyApi ----------


def test_ontology_api_list_object_types():
    api = OntologyApi()
    result = api.list_object_types()
    assert isinstance(result, list)


def test_ontology_api_get_unknown_returns_none():
    api = OntologyApi()
    assert api.get_object_type("ghost-otd") is None
