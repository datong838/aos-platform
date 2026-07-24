"""W1-1 · Function 表达式引擎 单元测试。

详见 docs/palantier/20_tech/220tech_function-engine.md §6。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.function_engine import (
    FunctionError,
    evaluate,
    infer_type,
    parse,
)
from aos_api.main import create_app


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #
class OntologyObjectStub:
    """模拟 Ontology 对象，供 getProperty / link 测试。"""

    def __init__(self, props: dict | None = None, links: dict | None = None) -> None:
        self._props = props or {}
        self._links = links or {}

    def get_property(self, name: str):
        return self._props.get(name)

    def link(self, name: str):
        return self._links.get(name, [])


def ev(text: str, context: dict | None = None):
    return evaluate(parse(text), context or {})


# --------------------------------------------------------------------------- #
# 引擎核心用例
# --------------------------------------------------------------------------- #
def test_arithmetic_expression():
    assert ev("1 + 2 * 3") == 7


def test_arithmetic_precedence():
    assert ev("(1 + 2) * 3") == 9


def test_string_concat():
    assert ev('"Hello" + " " + name', {"name": "World"}) == "Hello World"


def test_property_access():
    assert abs(ev("order.amount * 1.1", {"order": {"amount": 100}}) - 110.0) < 1e-9


def test_safe_property_access():
    assert ev("order?.customer?.name", {"order": None}) is None


def test_unsafe_property_access_null():
    with pytest.raises(FunctionError) as exc:
        ev("order.customer.name", {"order": None})
    assert exc.value.code == "NULL_DEREF"


def test_conditional_expression_true():
    assert ev('if amount > 100 then "大额" else "小额"', {"amount": 200}) == "大额"


def test_conditional_expression_false():
    assert ev('if amount > 100 then "大额" else "小额"', {"amount": 50}) == "小额"


def test_logical_and_short_circuit():
    # false && undefined_var 应短路，不触发 UNDEFINED_VAR
    assert ev("false && undefined_var") is False


def test_type_inference_number():
    assert infer_type(parse("1 + 2")) == "number"


def test_type_inference_string():
    assert infer_type(parse('"a" + "b"')) == "string"


def test_type_inference_boolean():
    assert infer_type(parse("1 > 2")) == "boolean"


def test_type_error_mismatch():
    with pytest.raises(FunctionError) as exc:
        ev('"a" + 1')
    assert exc.value.code == "TYPE_MISMATCH"


def test_division_by_zero():
    with pytest.raises(FunctionError) as exc:
        ev("1 / 0")
    assert exc.value.code == "DIVISION_BY_ZERO"


def test_undefined_variable():
    with pytest.raises(FunctionError) as exc:
        ev("undefined_var")
    assert exc.value.code == "UNDEFINED_VAR"


def test_parse_error_unexpected():
    with pytest.raises(FunctionError) as exc:
        ev("1 +")
    assert exc.value.code == "PARSE_ERROR"


def test_ontology_get_property():
    order = OntologyObjectStub({"amount": 100})
    assert ev('order.getProperty("amount")', {"order": order}) == 100


def test_builtin_len():
    assert ev("len(name)", {"name": "abc"}) == 3


def test_complex_expression():
    # amount=100, 100*2=200 > 150 → 大额（用整数系数避免浮点歧义）
    assert (
        ev('if order.amount * 2 > 150 then "大额" else "小额"', {"order": {"amount": 100}})
        == "大额"
    )


# --------------------------------------------------------------------------- #
# API 层用例
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_eval_endpoint(client):
    resp = client.post("/v1/functions/eval", json={"expression": "1 + 2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == 3
    assert body["type"] == "number"


def test_typecheck_endpoint(client):
    resp = client.post("/v1/functions/typecheck", json={"expression": "1 > 2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["inferred_type"] == "boolean"


def test_eval_error_400(client):
    resp = client.post("/v1/functions/eval", json={"expression": "1 / 0"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "DIVISION_BY_ZERO"


def test_eval_parse_error_400(client):
    resp = client.post("/v1/functions/eval", json={"expression": "1 +"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARSE_ERROR"
