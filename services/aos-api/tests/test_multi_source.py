"""W2-20 · Pipeline 多数据源支持 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.multi_source import DataSource, JoinConfig, MultiSourceEngine

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-w2-20",
}


def _engine_with_order_product_buyer():
    eng = MultiSourceEngine()
    msp = eng.create("order-product-buyer")
    eng.add_source(msp.id, DataSource(id="orders", name="订单", rows=[
        {"order_id": "O1", "product_id": "P1", "buyer_id": "B1", "amount": 100},
        {"order_id": "O2", "product_id": "P2", "buyer_id": "B1", "amount": 200},
        {"order_id": "O3", "product_id": "P1", "buyer_id": "B2", "amount": 150},
    ]))
    eng.add_source(msp.id, DataSource(id="products", name="商品", rows=[
        {"product_id": "P1", "product_name": "商品A", "price": 50},
        {"product_id": "P2", "product_name": "商品B", "price": 200},
    ]))
    eng.add_source(msp.id, DataSource(id="buyers", name="买家", rows=[
        {"buyer_id": "B1", "buyer_name": "张三"},
        {"buyer_id": "B2", "buyer_name": "李四"},
    ]))
    return eng, msp


# --------------------------------------------------------------------------- #
def test_single_source_passthrough():
    eng = MultiSourceEngine()
    msp = eng.create("single")
    eng.add_source(msp.id, DataSource(id="s1", rows=[{"a": 1}, {"a": 2}]))
    result = eng.execute(msp.id)
    assert len(result) == 2


def test_two_table_join():
    eng, msp = _engine_with_order_product_buyer()
    eng.add_join(msp.id, JoinConfig(
        left_source_id="orders", right_source_id="products",
        left_key="product_id", right_key="product_id", join_type="inner",
    ))
    result = eng.execute(msp.id)
    assert len(result) == 3
    r0 = [r for r in result if r["order_id"] == "O1"][0]
    assert r0["product_name"] == "商品A"


def test_three_table_join_chain():
    eng, msp = _engine_with_order_product_buyer()
    eng.add_join(msp.id, JoinConfig(
        left_source_id="orders", right_source_id="products",
        left_key="product_id", right_key="product_id",
    ))
    eng.add_join(msp.id, JoinConfig(
        left_source_id="orders", right_source_id="buyers",
        left_key="buyer_id", right_key="buyer_id",
    ))
    result = eng.execute(msp.id)
    assert len(result) == 3
    r0 = [r for r in result if r["order_id"] == "O1"][0]
    assert "product_name" in r0
    assert "buyer_name" in r0
    assert r0["buyer_name"] == "张三"


def test_left_join():
    eng = MultiSourceEngine()
    msp = eng.create("lj")
    eng.add_source(msp.id, DataSource(id="left", rows=[{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]))
    eng.add_source(msp.id, DataSource(id="right", rows=[{"id": 1, "name": "X"}]))
    eng.add_join(msp.id, JoinConfig(
        left_source_id="left", right_source_id="right",
        left_key="id", right_key="id", join_type="left",
    ))
    result = eng.execute(msp.id)
    assert len(result) == 2


def test_add_join_source_not_found():
    eng, msp = _engine_with_order_product_buyer()
    with pytest.raises(Exception):
        eng.add_join(msp.id, JoinConfig(
            left_source_id="orders", right_source_id="nonexistent",
            left_key="x", right_key="y",
        ))


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = MultiSourceEngine()
    monkeypatch.setattr("aos_api.routers.multi_source.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_create_and_add_source(client):
    resp = client.post("/v1/multi-source-pipelines", json={"name": "api-test"}, headers=_H)
    assert resp.status_code == 200
    msp_id = resp.json()["id"]

    resp = client.post(f"/v1/multi-source-pipelines/{msp_id}/sources", json={
        "source_id": "s1", "name": "源1", "rows": [{"id": 1}],
    }, headers=_H)
    assert resp.status_code == 200

    resp = client.post(f"/v1/multi-source-pipelines/{msp_id}/execute", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
