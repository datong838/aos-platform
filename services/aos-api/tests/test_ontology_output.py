"""W2-3 · Ontology 对象类型输出 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.ontology_output import (
    ObjectField,
    ObjectTypeDefinition,
    OntologyOutputStore,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-w2-3",
}


def _sample_otd(**kw) -> ObjectTypeDefinition:
    base = dict(
        name="Order",
        display_name="订单",
        primary_key="order_id",
        title_field="order_name",
        fields=[
            ObjectField(name="order_id", type="string"),
            ObjectField(name="order_name", type="string"),
            ObjectField(name="amount", type="number"),
            ObjectField(name="created_at", type="date"),
        ],
        source_dataset_rid="ri.dataset.orders",
        source_pipeline_id="pipeline-1",
    )
    base.update(kw)
    return ObjectTypeDefinition(**base)


# --------------------------------------------------------------------------- #
# 引擎层
# --------------------------------------------------------------------------- #
def test_define_and_get():
    store = OntologyOutputStore()
    otd = store.define(_sample_otd())
    assert otd.id
    got = store.get(otd.id)
    assert got is not None
    assert got.name == "Order"
    assert got.primary_key == "order_id"


def test_list_all():
    store = OntologyOutputStore()
    store.define(_sample_otd())
    store.define(_sample_otd(name="Product", primary_key="product_id",
                             fields=[ObjectField(name="product_id", type="string")]))
    assert len(store.list_all()) == 2


def test_delete():
    store = OntologyOutputStore()
    otd = store.define(_sample_otd())
    assert store.delete(otd.id) is True
    assert store.delete(otd.id) is False


def test_name_duplicate():
    store = OntologyOutputStore()
    store.define(_sample_otd())
    import pytest as _pt
    with _pt.raises(Exception):
        store.define(_sample_otd())


def test_pk_not_in_fields():
    store = OntologyOutputStore()
    with pytest.raises(Exception):
        store.define(_sample_otd(primary_key="nonexistent_field"))


def test_infer_fields():
    store = OntologyOutputStore()
    rows = [
        {"id": 1, "name": "a", "price": 9.9, "active": True},
        {"id": 2, "name": "b", "price": 10.5, "active": False},
    ]
    fields = store.infer_fields(rows)
    assert len(fields) == 4
    type_map = {f.name: f.type for f in fields}
    assert type_map["id"] == "number"
    assert type_map["name"] == "string"
    assert type_map["price"] == "number"
    assert type_map["active"] == "boolean"


def test_infer_fields_empty():
    store = OntologyOutputStore()
    assert store.infer_fields([]) == []


def test_preview_objects():
    store = OntologyOutputStore()
    otd = store.define(_sample_otd())
    rows = [
        {"order_id": "ORD-001", "order_name": "测试订单1", "amount": 100, "created_at": "2026-01-01"},
        {"order_id": "ORD-002", "order_name": "测试订单2", "amount": 200, "created_at": "2026-01-02"},
    ]
    objects = store.preview_objects(otd.id, rows)
    assert len(objects) == 2
    assert objects[0]["object_id"] == "ORD-001"
    assert objects[0]["title"] == "测试订单1"
    assert objects[0]["object_type"] == "Order"
    assert objects[0]["properties"]["amount"] == 100


def test_preview_objects_limit():
    store = OntologyOutputStore()
    otd = store.define(_sample_otd())
    rows = [{"order_id": f"ORD-{i:03d}", "order_name": f"订单{i}", "amount": i} for i in range(50)]
    objects = store.preview_objects(otd.id, rows, limit=10)
    assert len(objects) == 10


def test_preview_objects_skip_null_pk():
    store = OntologyOutputStore()
    otd = store.define(_sample_otd())
    rows = [
        {"order_id": None, "order_name": "无主键", "amount": 0},
        {"order_id": "ORD-001", "order_name": "有效", "amount": 100},
    ]
    objects = store.preview_objects(otd.id, rows)
    assert len(objects) == 1
    assert objects[0]["object_id"] == "ORD-001"


def test_get_by_name():
    store = OntologyOutputStore()
    store.define(_sample_otd())
    got = store.get_by_name("Order")
    assert got is not None
    assert got.primary_key == "order_id"
    assert store.get_by_name("NonExistent") is None


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    from aos_api.ontology_output import OntologyOutputStore
    fresh = OntologyOutputStore()
    monkeypatch.setattr("aos_api.routers.ontology_outputs.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_define_and_get(client):
    resp = client.post("/v1/ontology-outputs", json={
        "name": "Order",
        "primary_key": "order_id",
        "title_field": "order_name",
        "fields": [
            {"name": "order_id", "type": "string"},
            {"name": "order_name", "type": "string"},
        ],
        "source_dataset_rid": "ri.dataset.orders",
    }, headers=_H)
    assert resp.status_code == 200
    otd_id = resp.json()["id"]

    resp = client.get(f"/v1/ontology-outputs/{otd_id}", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Order"


def test_api_infer_fields(client):
    resp = client.post("/v1/ontology-outputs/infer-fields", json={
        "rows": [{"id": 1, "name": "x", "val": True}],
    }, headers=_H)
    assert resp.status_code == 200
    fields = resp.json()["fields"]
    assert len(fields) == 3


def test_api_preview(client):
    create = client.post("/v1/ontology-outputs", json={
        "name": "Product",
        "primary_key": "product_id",
        "fields": [
            {"name": "product_id", "type": "string"},
            {"name": "name", "type": "string"},
        ],
    }, headers=_H)
    otd_id = create.json()["id"]

    resp = client.post(f"/v1/ontology-outputs/{otd_id}/preview", json={
        "rows": [{"product_id": "P1", "name": "商品1"}],
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["objects"][0]["object_id"] == "P1"


def test_api_not_found(client):
    resp = client.get("/v1/ontology-outputs/nonexistent", headers=_H)
    assert resp.status_code == 404
