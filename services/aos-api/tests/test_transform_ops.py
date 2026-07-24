"""W1-8 · Transform 算子库 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.transform_ops import (
    TRANSFORM_REGISTRY,
    TransformError,
    apply_pipeline,
    apply_transform,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}

_ROWS = [
    {"id": 1, "name": "Alice", "amount": 100, "tags": ["a", "b"]},
    {"id": 2, "name": "Bob", "amount": 200, "tags": ["c"]},
    {"id": 3, "name": "Carol", "amount": 150, "tags": ["a", "d"]},
    {"id": 1, "name": "Alice2", "amount": 50, "tags": ["e"]},
]


def test_filter():
    result = apply_transform("filter", _ROWS, {"expression": "amount > 100"})
    assert len(result) == 2
    assert all(r["amount"] > 100 for r in result)


def test_join():
    right = [{"id": 1, "city": "NYC"}, {"id": 2, "city": "LA"}]
    result = apply_transform("join", _ROWS, {"right": right, "left_key": "id", "right_key": "id", "how": "inner"})
    assert len(result) == 3
    cities = [r.get("city") for r in result]
    assert "NYC" in cities


def test_aggregate():
    result = apply_transform("aggregate", _ROWS, {"group_by": ["id"], "aggregations": {"amount": "sum"}})
    assert len(result) == 3
    id1 = next(r for r in result if r["id"] == 1)
    assert id1["amount_sum"] == 150


def test_explode():
    result = apply_transform("explode", _ROWS[:1], {"field": "tags"})
    assert len(result) == 2
    assert result[0]["tags"] == "a"
    assert result[1]["tags"] == "b"


def test_cast():
    result = apply_transform("cast", [{"val": "42"}], {"field": "val", "type": "number"})
    assert result[0]["val"] == 42.0


def test_union():
    other = [{"id": 99, "name": "Zed", "amount": 0, "tags": []}]
    result = apply_transform("union", _ROWS, {"other": other})
    assert len(result) == 5


def test_sort():
    result = apply_transform("sort", _ROWS, {"field": "amount", "descending": True})
    amounts = [r["amount"] for r in result]
    assert amounts == sorted(amounts, reverse=True)


def test_distinct():
    result = apply_transform("distinct", _ROWS, {"fields": ["id"]})
    assert len(result) == 3


def test_expression():
    result = apply_transform("expression", _ROWS, {"output_field": "doubled", "expression": "amount * 2"})
    assert result[0]["doubled"] == 200


def test_unknown_op():
    with pytest.raises(TransformError) as exc:
        apply_transform("nonexistent", [], {})
    assert exc.value.code == "UNKNOWN_OP"


def test_pipeline_chain():
    steps = [
        {"op": "filter", "config": {"expression": "amount >= 100"}},
        {"op": "sort", "config": {"field": "amount", "descending": True}},
        {"op": "distinct", "config": {"fields": ["id"]}},
    ]
    result = apply_pipeline(_ROWS, steps)
    assert len(result) <= 3
    amounts = [r["amount"] for r in result]
    assert amounts == sorted(amounts, reverse=True)


def test_registry_has_fifteen_ops():
    """W2-#5 · 算子库从 9 个扩展到 15 个"""
    assert len(TRANSFORM_REGISTRY) >= 15
    for name in ["filter", "join", "aggregate", "explode", "cast", "union", "sort", "distinct", "expression",
                 "window", "pivot", "unpivot", "fillna", "normalize", "string_ops"]:
        assert name in TRANSFORM_REGISTRY


# --- API --- #
@pytest.fixture()
def client():
    return TestClient(create_app())


def test_api_list_transforms(client):
    resp = client.get("/v1/transforms", headers=_H)
    assert resp.status_code == 200
    assert "filter" in resp.json()["ops"]


def test_api_apply_transform(client):
    resp = client.post("/v1/transforms/apply", json={
        "op": "filter",
        "rows": [{"x": 1}, {"x": 2}],
        "config": {"expression": "x > 1"},
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_api_pipeline(client):
    resp = client.post("/v1/transforms/pipeline", json={
        "rows": [{"x": 1}, {"x": 2}, {"x": 3}],
        "steps": [{"op": "filter", "config": {"expression": "x >= 2"}}],
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_api_unknown_op_400(client):
    resp = client.post("/v1/transforms/apply", json={
        "op": "bogus", "rows": [], "config": {},
    }, headers=_H)
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# W2-#5 · 新增算子测试
# ──────────────────────────────────────────────────────────────


def test_window_row_number():
    rows = [
        {"dept": "A", "name": "X", "score": 90},
        {"dept": "A", "name": "Y", "score": 85},
        {"dept": "B", "name": "Z", "score": 95},
    ]
    result = apply_transform("window", rows, {
        "partition_by": ["dept"],
        "order_by": "score",
        "order_desc": True,
        "functions": [{"type": "row_number", "output": "rn"}],
    })
    assert len(result) == 3
    rn_values = {r["name"]: r["rn"] for r in result}
    assert rn_values["X"] == 1
    assert rn_values["Y"] == 2
    assert rn_values["Z"] == 1  # 不同分区独立编号


def test_window_running_sum():
    rows = [
        {"dept": "A", "amount": 10},
        {"dept": "A", "amount": 20},
        {"dept": "A", "amount": 30},
    ]
    result = apply_transform("window", rows, {
        "partition_by": ["dept"],
        "order_by": "amount",
        "functions": [{"type": "running_sum", "field": "amount", "output": "cumsum"}],
    })
    assert len(result) == 3
    assert result[0]["cumsum"] == 10
    assert result[1]["cumsum"] == 30
    assert result[2]["cumsum"] == 60


def test_window_lag_lead():
    rows = [
        {"group": "G", "val": 1},
        {"group": "G", "val": 2},
        {"group": "G", "val": 3},
    ]
    result = apply_transform("window", rows, {
        "partition_by": ["group"],
        "order_by": "val",
        "functions": [
            {"type": "lag", "field": "val", "output": "prev", "N": 1},
            {"type": "lead", "field": "val", "output": "next", "N": 1},
        ],
    })
    assert result[0]["prev"] is None
    assert result[0]["next"] == 2
    assert result[1]["prev"] == 1
    assert result[1]["next"] == 3
    assert result[2]["prev"] == 2
    assert result[2]["next"] is None


def test_pivot():
    rows = [
        {"product": "A", "region": "East", "sales": 10},
        {"product": "A", "region": "West", "sales": 20},
        {"product": "B", "region": "East", "sales": 30},
    ]
    result = apply_transform("pivot", rows, {
        "group_by": ["product"],
        "pivot_column": "region",
        "value_column": "sales",
        "aggregation": "sum",
    })
    result_map = {r["product"]: r for r in result}
    assert result_map["A"]["East"] == 10
    assert result_map["A"]["West"] == 20
    assert result_map["B"]["East"] == 30
    assert result_map["B"].get("West") is None


def test_unpivot():
    rows = [
        {"id": 1, "jan": 100, "feb": 200},
        {"id": 2, "jan": 300, "feb": 400},
    ]
    result = apply_transform("unpivot", rows, {
        "id_columns": ["id"],
        "value_columns": ["jan", "feb"],
        "variable_column": "month",
        "value_column": "amount",
    })
    assert len(result) == 4
    month_map = {(r["id"], r["month"]): r["amount"] for r in result}
    assert month_map[(1, "jan")] == 100
    assert month_map[(1, "feb")] == 200
    assert month_map[(2, "jan")] == 300
    assert month_map[(2, "feb")] == 400


def test_fillna_constant():
    rows = [{"a": 1}, {"a": None}, {"a": 3}]
    result = apply_transform("fillna", rows, {"columns": ["a"], "method": "constant", "value": 0})
    assert result[1]["a"] == 0


def test_fillna_ffill():
    rows = [{"a": 1}, {"a": None}, {"a": None}, {"a": 4}]
    result = apply_transform("fillna", rows, {"columns": ["a"], "method": "ffill"})
    assert result[0]["a"] == 1
    assert result[1]["a"] == 1  # 前向填充
    assert result[2]["a"] == 1  # 前向填充
    assert result[3]["a"] == 4


def test_fillna_mean():
    rows = [{"x": 10}, {"x": 20}, {"x": None}]
    result = apply_transform("fillna", rows, {"columns": ["x"], "method": "mean"})
    assert result[2]["x"] == 15.0


def test_normalize_minmax():
    rows = [{"x": 0}, {"x": 50}, {"x": 100}]
    result = apply_transform("normalize", rows, {"columns": ["x"], "method": "minmax"})
    assert result[0]["x_norm"] == 0.0
    assert result[1]["x_norm"] == 0.5
    assert result[2]["x_norm"] == 1.0


def test_normalize_zscore():
    import math
    rows = [{"x": 10}, {"x": 20}, {"x": 30}]
    result = apply_transform("normalize", rows, {"columns": ["x"], "method": "zscore"})
    assert abs(result[0]["x_norm"] - (-1.225)) < 0.01  # z-score ≈ -1.225
    assert abs(result[1]["x_norm"]) < 0.01  # ≈ 0
    assert abs(result[2]["x_norm"] - 1.225) < 0.01  # ≈ 1.225


def test_string_ops_upper():
    rows = [{"name": "alice"}, {"name": "bob"}]
    result = apply_transform("string_ops", rows, {
        "operations": [{"column": "name", "function": "upper", "output": "name_upper"}],
    })
    assert result[0]["name_upper"] == "ALICE"
    assert result[1]["name_upper"] == "BOB"


def test_string_ops_length_and_replace():
    rows = [{"text": "hello"}, {"text": "world"}]
    result = apply_transform("string_ops", rows, {
        "operations": [
            {"column": "text", "function": "length", "output": "len"},
            {"column": "text", "function": "replace", "args": ["o", "O"], "output": "replaced"},
        ],
    })
    assert result[0]["len"] == 5
    assert result[1]["replaced"] == "wOrld"


def test_api_scalar_functions(client):
    """W2-#5 · GET /v1/transforms/functions 返回函数目录"""
    resp = client.get("/v1/transforms/functions", headers=_H)
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "functions" in data
    assert data["total"] >= 50
    # 验证分类
    assert "数值" in data["categories"]
    assert "字符串" in data["categories"]
    assert "abs" in [f["name"] for f in data["functions"]]
