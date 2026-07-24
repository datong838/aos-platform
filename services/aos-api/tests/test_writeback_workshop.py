"""W2-#19 · 写回 Workshop 绑定 单元测试。

详见 docs/palantier/20_tech/220tech_w2-f-funnel-logic-writeback.md §2.3。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.writeback import WritebackError, WritebackOp, WritebackStore

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-ws",
}


def _new_store() -> WritebackStore:
    return WritebackStore()


def _seed_layer(store: WritebackStore, ds: str = "ds.1") -> str:
    txn = store.begin(ds)
    store.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1, "name": "a"})])
    store.commit(txn)
    return txn


# --------------------------------------------------------------------------- #
# 引擎：bind / unbind
# --------------------------------------------------------------------------- #
def test_bind_workshop():
    s = _new_store()
    _seed_layer(s, "ds.1")
    layer = s.bind_workshop("ds.1", "mod-orders")
    assert layer.workshop_module == "mod-orders"
    assert layer.workshop_bound_at is not None


def test_bind_workshop_empty_module_rejected():
    s = _new_store()
    _seed_layer(s, "ds.1")
    with pytest.raises(WritebackError) as exc:
        s.bind_workshop("ds.1", "")
    assert exc.value.code == "BAD_MODULE"


def test_bind_workshop_no_layer_not_found():
    s = _new_store()
    with pytest.raises(WritebackError) as exc:
        s.bind_workshop("ds.none", "mod")
    assert exc.value.code == "NOT_FOUND"


def test_unbind_workshop():
    s = _new_store()
    _seed_layer(s, "ds.1")
    s.bind_workshop("ds.1", "mod")
    layer = s.unbind_workshop("ds.1")
    assert layer.workshop_module is None
    assert layer.workshop_bound_at is None


def test_unbind_workshop_no_layer_not_found():
    s = _new_store()
    with pytest.raises(WritebackError) as exc:
        s.unbind_workshop("ds.none")
    assert exc.value.code == "NOT_FOUND"


def test_list_by_workshop():
    s = _new_store()
    _seed_layer(s, "ds.1")
    _seed_layer(s, "ds.2")
    s.bind_workshop("ds.1", "mod-a")
    s.bind_workshop("ds.2", "mod-b")
    a = s.list_by_workshop("mod-a")
    b = s.list_by_workshop("mod-b")
    assert len(a) == 1
    assert a[0].dataset_rid == "ds.1"
    assert len(b) == 1
    assert b[0].dataset_rid == "ds.2"


def test_list_by_workshop_empty():
    s = _new_store()
    assert s.list_by_workshop("mod-none") == []


def test_layer_default_no_workshop():
    s = _new_store()
    txn = s.begin("ds.1")
    layer = s.get_txn(txn)
    assert layer.workshop_module is None
    assert layer.workshop_bound_at is None


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = WritebackStore()
    monkeypatch.setattr("aos_api.routers.writeback.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_bind_workshop(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.ws1"}, headers=_H).json()["txn_id"]
    client.post(f"/v1/writeback/{txn}/apply", json={
        "ops": [{"op": "upsert", "pk": "1", "row": {"id": 1}}],
    }, headers=_H)
    client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    resp = client.post("/v1/writeback/datasets/ds.ws1/bind-workshop", json={
        "module_id": "mod-orders",
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["workshop_module"] == "mod-orders"


def test_api_unbind_workshop(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.ws2"}, headers=_H).json()["txn_id"]
    client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    client.post("/v1/writeback/datasets/ds.ws2/bind-workshop", json={"module_id": "mod"}, headers=_H)
    resp = client.post("/v1/writeback/datasets/ds.ws2/unbind-workshop", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["workshop_module"] is None


def test_api_workshop_preview(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.ws3"}, headers=_H).json()["txn_id"]
    client.post(f"/v1/writeback/{txn}/apply", json={
        "ops": [
            {"op": "upsert", "pk": "1", "row": {"id": 1}},
            {"op": "soft_delete", "pk": "2"},
        ],
    }, headers=_H)
    client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    client.post("/v1/writeback/datasets/ds.ws3/bind-workshop", json={"module_id": "mod-prev"}, headers=_H)
    resp = client.get("/v1/writeback/workshop/mod-prev/preview", headers=_H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["entry_count"] == 2
    assert body["items"][0]["deleted_count"] == 1


def test_api_bind_workshop_not_found_404(client):
    resp = client.post("/v1/writeback/datasets/ds.none/bind-workshop", json={
        "module_id": "mod",
    }, headers=_H)
    assert resp.status_code == 404
