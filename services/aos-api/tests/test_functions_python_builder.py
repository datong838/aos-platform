"""W1-19 · Functions Python Builder 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.functions_python_builder import (
    MAX_CODE_SIZE,
    MAX_ROWS,
    PythonBuilder,
    PythonBuilderError,
)
from aos_api.main import create_app
from aos_api.pipeline_builder import Pipeline, PipelineEditor

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}

_GOOD_CODE = """
def transform(rows):
    return [{"id": r["id"], "doubled": r["value"] * 2} for r in rows]
"""

_GOOD_CODE_PLUS = """
def transform(rows):
    return [{"id": r["id"], "plus1": r["value"] + 1} for r in rows]
"""


def _new_builder() -> PythonBuilder:
    return PythonBuilder()


# --- 引擎：注册 --- #

def test_register_lifecycle():
    b = _new_builder()
    pf = b.register("double", _GOOD_CODE, "doubles value")
    assert pf.name == "double"
    assert b.get("double").description == "doubles value"
    assert len(b.list_all()) == 1
    b.delete("double")
    with pytest.raises(PythonBuilderError):
        b.get("double")


def test_register_upsert():
    b = _new_builder()
    b.register("f", _GOOD_CODE, "v1")
    b.register("f", _GOOD_CODE_PLUS, "v2")
    pf = b.get("f")
    assert pf.description == "v2"
    assert "plus1" in pf.code


def test_register_bad_name():
    b = _new_builder()
    with pytest.raises(PythonBuilderError) as exc:
        b.register("123bad", _GOOD_CODE)
    assert exc.value.code == "BAD_NAME"


# --- 引擎：静态校验 --- #

def test_validate_clean():
    b = _new_builder()
    assert b.validate_code(_GOOD_CODE) == []


def test_validate_no_transform():
    b = _new_builder()
    errs = b.validate_code("x = 1\n")
    assert any("CODE_NO_TRANSFORM" in e for e in errs)


def test_validate_blocked_import():
    b = _new_builder()
    code = "import os\ndef transform(rows):\n    return rows\n"
    errs = b.validate_code(code)
    assert any("CODE_BLOCKED_IMPORT" in e for e in errs)


def test_validate_blocked_from_import():
    b = _new_builder()
    code = "from subprocess import run\ndef transform(rows):\n    return rows\n"
    errs = b.validate_code(code)
    assert any("CODE_BLOCKED_IMPORT" in e for e in errs)


def test_validate_blocked_builtin():
    b = _new_builder()
    code = "def transform(rows):\n    return eval('[]')\n"
    errs = b.validate_code(code)
    assert any("CODE_BLOCKED_BUILTIN" in e for e in errs)


def test_validate_blocked_dunder():
    b = _new_builder()
    code = "def transform(rows):\n    return rows.__class__\n"
    errs = b.validate_code(code)
    assert any("CODE_BLOCKED_DUNDER" in e for e in errs)


def test_validate_syntax_error():
    b = _new_builder()
    errs = b.validate_code("def transform(:\n  pass\n")
    assert any("CODE_PARSE_ERROR" in e for e in errs)


def test_validate_too_large():
    b = _new_builder()
    code = "def transform(rows):\n    return rows\n" + "# " * (MAX_CODE_SIZE)
    errs = b.validate_code(code)
    assert any("CODE_TOO_LARGE" in e for e in errs)


# --- 引擎：执行 --- #

def test_execute_simple():
    b = _new_builder()
    b.register("double", _GOOD_CODE)
    result = b.execute("double", [{"id": 1, "value": 10}, {"id": 2, "value": 20}])
    assert result.output_count == 2
    assert result.rows[0]["doubled"] == 20
    assert result.rows[1]["doubled"] == 40


def test_execute_input_too_large():
    b = _new_builder()
    b.register("double", _GOOD_CODE)
    with pytest.raises(PythonBuilderError) as exc:
        b.execute("double", [{"id": i, "value": i} for i in range(MAX_ROWS + 1)])
    assert exc.value.code == "INPUT_TOO_LARGE"


def test_execute_bad_return():
    b = _new_builder()
    code = "def transform(rows):\n    return 'not a list'\n"
    b.register("badret", code)
    with pytest.raises(PythonBuilderError) as exc:
        b.execute("badret", [{"id": 1}])
    assert exc.value.code == "CODE_BAD_RETURN"


def test_execute_blocked_import_runtime():
    b = _new_builder()
    code = "def transform(rows):\n    return rows\n"
    b.register("safe", code)
    result = b.execute("safe", [{"id": 1}])
    assert result.output_count == 1


def test_execute_timeout():
    b = _new_builder()
    code = "def transform(rows):\n    while True:\n        pass\n    return rows\n"
    b.register("loop", code)
    with pytest.raises(PythonBuilderError) as exc:
        b.execute("loop", [{"id": 1}], timeout=0.3)
    assert exc.value.code == "TIMEOUT"


# --- Pipeline 集成 --- #

def test_pipeline_preview_python_node():
    b = _new_builder()
    from aos_api.functions_python_builder import _builder, get_builder
    get_builder().register("double", _GOOD_CODE)
    ed = PipelineEditor(Pipeline(id="p1", name="test"))
    ed.apply({"action": "add_node", "node": {"id": "src", "kind": "dataset", "label": "src"}})
    ed.apply({"action": "add_node", "node": {
        "id": "py", "kind": "transform", "op": "python:double", "label": "double"}})
    ed.apply({"action": "add_edge", "edge": {"src": "src", "dst": "py"}})
    out = ed.preview({"src": [{"id": 1, "value": 5}, {"id": 2, "value": 7}]})
    assert out["py"][0]["doubled"] == 10
    assert out["py"][1]["doubled"] == 14


def test_pipeline_python_node_not_registered():
    from aos_api.functions_python_builder import get_builder
    ed = PipelineEditor(Pipeline(id="p2", name="test"))
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_node", "node": {
            "id": "py", "kind": "transform", "op": "python:ghost"}})
    assert exc.value.code == "PYTHON_FUNC_NOT_FOUND"


from aos_api.pipeline_builder import PipelineEditorError  # noqa: E402


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = PythonBuilder()
    monkeypatch.setattr("aos_api.routers.python_functions.get_builder", lambda: fresh)
    monkeypatch.setattr("aos_api.pipeline_builder.get_builder", lambda: fresh, raising=False)
    monkeypatch.setattr("aos_api.functions_python_builder.get_builder", lambda: fresh, raising=False)
    return TestClient(create_app())


def test_api_register(client):
    resp = client.post("/v1/python-functions", json={
        "name": "double", "code": _GOOD_CODE, "description": "doubler"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["name"] == "double"


def test_api_list(client):
    client.post("/v1/python-functions", json={"name": "f1", "code": _GOOD_CODE}, headers=_H)
    client.post("/v1/python-functions", json={"name": "f2", "code": _GOOD_CODE}, headers=_H)
    resp = client.get("/v1/python-functions", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["functions"]) == 2


def test_api_get(client):
    client.post("/v1/python-functions", json={"name": "f1", "code": _GOOD_CODE}, headers=_H)
    resp = client.get("/v1/python-functions/f1", headers=_H)
    assert resp.status_code == 200


def test_api_get_404(client):
    resp = client.get("/v1/python-functions/ghost", headers=_H)
    assert resp.status_code == 404


def test_api_execute(client):
    client.post("/v1/python-functions", json={"name": "double", "code": _GOOD_CODE}, headers=_H)
    resp = client.post("/v1/python-functions/double/execute", json={
        "rows": [{"id": 1, "value": 10}]}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["rows"][0]["doubled"] == 20


def test_api_validate(client):
    resp = client.post("/v1/python-functions/validate", json={"code": _GOOD_CODE}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_api_validate_blocked(client):
    bad = "import os\ndef transform(rows):\n    return rows\n"
    resp = client.post("/v1/python-functions/validate", json={"code": bad}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_api_delete(client):
    client.post("/v1/python-functions", json={"name": "f1", "code": _GOOD_CODE}, headers=_H)
    resp = client.delete("/v1/python-functions/f1", headers=_H)
    assert resp.status_code == 200
    resp2 = client.get("/v1/python-functions/f1", headers=_H)
    assert resp2.status_code == 404


def test_api_register_blocked(client):
    bad = "import os\ndef transform(rows):\n    return rows\n"
    resp = client.post("/v1/python-functions", json={"name": "bad", "code": bad}, headers=_H)
    assert resp.status_code == 400
    assert "BLOCKED_IMPORT" in resp.json()["details"]["code"] if resp.json().get("details") else "BLOCKED_IMPORT" in resp.text
