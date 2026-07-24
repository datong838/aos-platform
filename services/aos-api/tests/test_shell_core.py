"""W1-7 · 壳核模式单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.shell_core import ActSpec, FuncSpec, ShellCore, ShellCoreError, WritebackTarget
from aos_api.writeback import WritebackStore

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _new_core() -> ShellCore:
    return ShellCore()


# --- 引擎：注册 --- #

def test_register_func():
    c = _new_core()
    c.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    assert c.get_func("add").ref == "a + b"


def test_register_action():
    c = _new_core()
    c.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    c.register_action(ActSpec(name="sum", func_ref="add"))
    assert c.get_action("sum").func_ref == "add"


def test_register_action_func_not_found():
    c = _new_core()
    with pytest.raises(ShellCoreError) as exc:
        c.register_action(ActSpec(name="bad", func_ref="ghost"))
    assert exc.value.code == "FUNC_NOT_FOUND"


def test_get_func_not_found():
    c = _new_core()
    with pytest.raises(ShellCoreError) as exc:
        c.get_func("ghost")
    assert exc.value.code == "FUNC_NOT_FOUND"


# --- 引擎：执行 expression --- #

def test_execute_expression():
    c = _new_core()
    c.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    c.register_action(ActSpec(name="sum", func_ref="add"))
    result = c.execute("sum", {"a": 2, "b": 3})
    assert result.func_result == 5
    assert result.mapped == {"result": 5}


def test_execute_with_mapping():
    c = _new_core()
    c.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    c.register_action(ActSpec(
        name="sum", func_ref="add",
        output_mapping={"total": "result", "doubled": "result * 2"},
    ))
    result = c.execute("sum", {"a": 2, "b": 3})
    assert result.mapped["total"] == 5
    assert result.mapped["doubled"] == 10


# --- 引擎：执行 python --- #

def test_execute_python():
    from aos_api.functions_python_builder import get_builder
    get_builder().register("doubler", "def transform(rows):\n    return [{**r, 'doubled': r['x'] * 2} for r in rows]\n")
    c = _new_core()
    c.register_func(FuncSpec(name="dbl", kind="python", ref="doubler"))
    c.register_action(ActSpec(name="double_it", func_ref="dbl"))
    result = c.execute("double_it", {"x": 21})
    assert result.func_result["doubled"] == 42


# --- 引擎：输入校验 --- #

def test_execute_input_missing():
    c = _new_core()
    c.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    c.register_action(ActSpec(name="sum", func_ref="add", input_schema={"a": "number", "b": "number"}))
    with pytest.raises(ShellCoreError) as exc:
        c.execute("sum", {"a": 1})
    assert exc.value.code == "INPUT_MISSING"


def test_execute_input_type_mismatch():
    c = _new_core()
    c.register_func(FuncSpec(name="add", kind="expression", ref="a + b"))
    c.register_action(ActSpec(name="sum", func_ref="add", input_schema={"a": "number"}))
    with pytest.raises(ShellCoreError) as exc:
        c.execute("sum", {"a": "not a number"})
    assert exc.value.code == "INPUT_TYPE_MISMATCH"


def test_execute_input_boolean_rejected_as_number():
    c = _new_core()
    c.register_func(FuncSpec(name="echo", kind="expression", ref="a"))
    c.register_action(ActSpec(name="echo", func_ref="echo", input_schema={"a": "number"}))
    with pytest.raises(ShellCoreError) as exc:
        c.execute("echo", {"a": True})
    assert exc.value.code == "INPUT_TYPE_MISMATCH"


# --- 引擎：错误路径 --- #

def test_execute_act_not_found():
    c = _new_core()
    with pytest.raises(ShellCoreError) as exc:
        c.execute("ghost", {})
    assert exc.value.code == "ACT_NOT_FOUND"


def test_execute_func_error():
    c = _new_core()
    c.register_func(FuncSpec(name="bad", kind="expression", ref="a +"))
    c.register_action(ActSpec(name="broken", func_ref="bad"))
    with pytest.raises(ShellCoreError) as exc:
        c.execute("broken", {"a": 1})
    assert exc.value.code == "FUNC_EXEC_ERROR"


# --- 引擎：writeback 集成 --- #

def test_execute_writeback_upsert(monkeypatch):
    fresh_wb = WritebackStore()
    monkeypatch.setattr("aos_api.shell_core.get_writeback_store", lambda: fresh_wb)
    c = _new_core()
    c.register_func(FuncSpec(name="id_echo", kind="expression", ref="id"))
    c.register_action(ActSpec(
        name="create", func_ref="id_echo",
        writeback=WritebackTarget(dataset_rid="ds.users", pk_field="id", op="upsert", row_from="params"),
    ))
    result = c.execute("create", {"id": 42, "label": "alice"})
    assert result.writeback_txn is not None
    assert result.writeback_error is None
    rows = fresh_wb.view("ds.users", [], "id")
    assert any(r.get("id") == 42 and r.get("label") == "alice" for r in rows)


def test_execute_writeback_soft_delete(monkeypatch):
    fresh_wb = WritebackStore()
    monkeypatch.setattr("aos_api.shell_core.get_writeback_store", lambda: fresh_wb)
    c = _new_core()
    c.register_func(FuncSpec(name="id_echo", kind="expression", ref="id"))
    c.register_action(ActSpec(
        name="del", func_ref="id_echo",
        writeback=WritebackTarget(dataset_rid="ds.users", pk_field="id", op="soft_delete"),
    ))
    result = c.execute("del", {"id": 99})
    assert result.writeback_txn is not None
    base = [{"id": 99, "name": "ghost"}]
    rows = fresh_wb.view("ds.users", base, "id")
    assert all(r.get("id") != 99 for r in rows)


def test_execute_writeback_missing_pk(monkeypatch):
    fresh_wb = WritebackStore()
    monkeypatch.setattr("aos_api.shell_core.get_writeback_store", lambda: fresh_wb)
    c = _new_core()
    c.register_func(FuncSpec(name="lit", kind="expression", ref="1"))
    c.register_action(ActSpec(
        name="no_pk", func_ref="lit",
        writeback=WritebackTarget(dataset_rid="ds.x", pk_field="missing"),
    ))
    result = c.execute("no_pk", {})
    assert result.writeback_txn is None
    assert "missing pk" in (result.writeback_error or "")


def test_execute_no_writeback():
    c = _new_core()
    c.register_func(FuncSpec(name="echo", kind="expression", ref="x"))
    c.register_action(ActSpec(name="e", func_ref="echo"))
    result = c.execute("e", {"x": "hello"})
    assert result.writeback_txn is None
    assert result.writeback_error is None


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    from aos_api.shell_core import ShellCore
    fresh = ShellCore()
    monkeypatch.setattr("aos_api.routers.shell_core.get_core", lambda: fresh)
    return TestClient(create_app())


def test_api_register_func(client):
    resp = client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    assert resp.status_code == 200


def test_api_list_funcs(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    resp = client.get("/v1/shell-core/funcs", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["funcs"]) == 1


def test_api_register_action(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    resp = client.post("/v1/shell-core/actions", json={
        "name": "sum", "func_ref": "add"}, headers=_H)
    assert resp.status_code == 200


def test_api_register_action_func_not_found(client):
    resp = client.post("/v1/shell-core/actions", json={
        "name": "bad", "func_ref": "ghost"}, headers=_H)
    assert resp.status_code == 404


def test_api_execute(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    client.post("/v1/shell-core/actions", json={
        "name": "sum", "func_ref": "add"}, headers=_H)
    resp = client.post("/v1/shell-core/actions/sum/execute", json={
        "params": {"a": 2, "b": 3}}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["func_result"] == 5


def test_api_execute_404(client):
    resp = client.post("/v1/shell-core/actions/ghost/execute", json={"params": {}}, headers=_H)
    assert resp.status_code == 404


def test_api_get_func_404(client):
    resp = client.get("/v1/shell-core/funcs/ghost", headers=_H)
    assert resp.status_code == 404


def test_api_get_action_detail(client):
    client.post("/v1/shell-core/funcs", json={
        "name": "add", "kind": "expression", "ref": "a + b"}, headers=_H)
    client.post("/v1/shell-core/actions", json={"name": "sum", "func_ref": "add"}, headers=_H)
    resp = client.get("/v1/shell-core/actions/sum", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["name"] == "sum"
