"""W1-18 · OMA Function Type 视图单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.function_type_view import (
    CodeLocation,
    FunctionRegistry,
    FunctionTypeError,
)
from aos_api.functions_python_builder import PythonBuilder
from aos_api.main import create_app
from aos_api.shell_core import ActSpec, FuncSpec, ShellCore

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}

_GOOD_CODE = "def transform(rows):\n    return [{**r, 'out': r['x'] * 2} for r in rows]\n"


def _setup(monkeypatch):
    core = ShellCore()
    py_builder = PythonBuilder()
    registry = FunctionRegistry()
    monkeypatch.setattr("aos_api.shell_core.get_core", lambda: core)
    monkeypatch.setattr("aos_api.functions_python_builder.get_builder", lambda: py_builder)
    return core, py_builder, registry


# --- 引擎：聚合 --- #

def test_aggregate_empty(monkeypatch):
    _, _, registry = _setup(monkeypatch)
    assert registry.aggregate_all() == []


def test_aggregate_expression(monkeypatch):
    core, _, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    views = registry.aggregate_all()
    assert len(views) == 1
    assert views[0].kind == "expression"
    assert "a + b" in views[0].signature


def test_aggregate_python(monkeypatch):
    _, py_builder, registry = _setup(monkeypatch)
    py_builder.register("doubler", _GOOD_CODE)
    views = registry.aggregate_all()
    assert len(views) == 1
    assert views[0].kind == "python"
    assert "transform(rows" in views[0].signature


def test_aggregate_mixed(monkeypatch):
    core, py_builder, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    py_builder.register("doubler", _GOOD_CODE)
    views = registry.aggregate_all()
    assert len(views) == 2
    kinds = {v.kind for v in views}
    assert kinds == {"expression", "python"}


def test_get_view_not_found(monkeypatch):
    _, _, registry = _setup(monkeypatch)
    with pytest.raises(FunctionTypeError) as exc:
        registry.get_view("ghost")
    assert exc.value.code == "NOT_FOUND"


# --- 引擎：使用历史 --- #

def test_record_and_get_usage(monkeypatch):
    core, _, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    registry.record_usage("add", "action:sum")
    registry.record_usage("add", "pipeline:p1/node:flt", "pipeline_node")
    usage = registry.get_usage("add")
    assert len(usage) == 2
    assert usage[0].used_in == "action:sum"


def test_usage_count_in_view(monkeypatch):
    core, _, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    registry.record_usage("add", "action:sum")
    view = registry.get_view("add")
    assert view.usage_count == 1


# --- 引擎：版本历史 --- #

def test_record_version(monkeypatch):
    core, _, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    registry.record_version("add", {"ref": "a + b"}, "alice")
    registry.record_version("add", {"ref": "a + b + c"}, "bob")
    versions = registry.get_versions("add")
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2
    assert versions[1].recorded_by == "bob"


def test_version_count_in_view(monkeypatch):
    core, _, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    registry.record_version("add", {"ref": "a + b"})
    view = registry.get_view("add")
    assert view.version_count == 1


# --- 引擎：代码位置 --- #

def test_set_code_location(monkeypatch):
    core, _, registry = _setup(monkeypatch)
    core.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    loc = CodeLocation(repo="aos", path="funcs.py", line=42, url="https://git/aos/funcs.py#L42")
    registry.set_code_location("add", loc)
    view = registry.get_view("add")
    assert view.latest_code_location is not None
    assert view.latest_code_location.line == 42


def test_usage_for_unknown_function_empty(monkeypatch):
    _, _, registry = _setup(monkeypatch)
    assert registry.get_usage("ghost") == []


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    core = ShellCore()
    py_builder = PythonBuilder()
    registry = FunctionRegistry()
    monkeypatch.setattr("aos_api.routers.function_types.get_registry", lambda: registry)
    monkeypatch.setattr("aos_api.shell_core.get_core", lambda: core)
    monkeypatch.setattr("aos_api.routers.shell_core.get_core", lambda: core)
    monkeypatch.setattr("aos_api.functions_python_builder.get_builder", lambda: py_builder)
    monkeypatch.setattr("aos_api.routers.python_functions.get_builder", lambda: py_builder)
    monkeypatch.setattr("aos_api.function_type_view.get_registry", lambda: registry, raising=False)
    return TestClient(create_app())


def test_api_list_empty(client):
    resp = client.get("/v1/oma/function-types", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_api_list_with_funcs(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    resp = client.get("/v1/oma/function-types", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_api_get_detail(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    resp = client.get("/v1/oma/function-types/add", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["name"] == "add"


def test_api_get_detail_404(client):
    resp = client.get("/v1/oma/function-types/ghost", headers=_H)
    assert resp.status_code == 404


def test_api_usage(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    client.post("/v1/oma/function-types/add/record-usage", json={
        "used_in": "action:sum"}, headers=_H)
    resp = client.get("/v1/oma/function-types/add/usage", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["usage"]) == 1


def test_api_versions(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    client.post("/v1/oma/function-types/add/record-version", json={
        "snapshot": {"ref": "a + b"}, "recorded_by": "alice"}, headers=_H)
    resp = client.get("/v1/oma/function-types/add/versions", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["versions"]) == 1


def test_api_code_location(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    resp = client.post("/v1/oma/function-types/add/code-location", json={
        "repo": "aos", "path": "funcs.py", "line": 42}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["line"] == 42
    detail = client.get("/v1/oma/function-types/add", headers=_H).json()
    assert detail["latest_code_location"]["line"] == 42
