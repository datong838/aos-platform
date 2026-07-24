"""W1-6 · Action 写回协议单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.writeback import WritebackError, WritebackOp, WritebackStore

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _new_store() -> WritebackStore:
    return WritebackStore()


# --- 引擎：事务生命周期 --- #

def test_begin_returns_txn_id():
    s = _new_store()
    txn_id = s.begin("ds.ri.1")
    assert txn_id.startswith("wb-")
    assert s.get_layer("ds.ri.1") is not None


def test_begin_duplicate_dataset_while_open():
    s = _new_store()
    s.begin("ds.ri.1")
    with pytest.raises(WritebackError) as exc:
        s.begin("ds.ri.1")
    assert exc.value.code == "TXN_OPEN"


def test_begin_after_commit_ok():
    s = _new_store()
    txn_id = s.begin("ds.ri.1")
    s.commit(txn_id)
    new_txn = s.begin("ds.ri.1")
    assert new_txn != txn_id


def test_apply_upsert_new():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    layer = s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1, "name": "alice"})])
    assert "1" in layer.entries
    assert layer.entries["1"].row["name"] == "alice"
    assert layer.entries["1"].version == 1


def test_apply_upsert_merge():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1, "name": "alice"})])
    layer = s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"age": 30})])
    assert layer.entries["1"].row["name"] == "alice"
    assert layer.entries["1"].row["age"] == 30
    assert layer.entries["1"].version == 2


def test_apply_soft_delete():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1})])
    layer = s.apply(txn, [WritebackOp(op="soft_delete", pk="1")])
    assert layer.entries["1"].deleted is True
    assert layer.entries["1"].version == 2


def test_apply_undelete():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1})])
    s.apply(txn, [WritebackOp(op="soft_delete", pk="1")])
    layer = s.apply(txn, [WritebackOp(op="undelete", pk="1")])
    assert layer.entries["1"].deleted is False
    assert layer.entries["1"].version == 3


def test_apply_undelete_missing():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    with pytest.raises(WritebackError) as exc:
        s.apply(txn, [WritebackOp(op="undelete", pk="ghost")])
    assert exc.value.code == "ENTRY_NOT_FOUND"


def test_commit_status():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    layer = s.commit(txn)
    assert layer.status == "committed"
    assert layer.committed_at is not None


def test_apply_after_commit_rejected():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.commit(txn)
    with pytest.raises(WritebackError) as exc:
        s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1})])
    assert exc.value.code == "TXN_CLOSED"


def test_rollback_status():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"id": 1})])
    layer = s.rollback(txn)
    assert layer.status == "rolled_back"


def test_apply_unknown_txn():
    s = _new_store()
    with pytest.raises(WritebackError) as exc:
        s.apply("ghost", [WritebackOp(op="upsert", pk="1", row={})])
    assert exc.value.code == "NOT_FOUND"


# --- 引擎：view 合并 --- #

def test_view_merge_upsert():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="upsert", pk="2", row={"id": 2, "name": "bob"})])
    s.commit(txn)
    base = [{"id": 1, "name": "alice"}, {"id": 2, "name": "old_bob"}, {"id": 3, "name": "carol"}]
    rows = s.view("ds.ri.1", base, "id")
    names = {r["name"] for r in rows}
    assert names == {"alice", "bob", "carol"}


def test_view_merge_soft_delete():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="soft_delete", pk="2")])
    s.commit(txn)
    base = [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}, {"id": 3, "name": "carol"}]
    rows = s.view("ds.ri.1", base, "id")
    pks = {r["id"] for r in rows}
    assert pks == {1, 3}


def test_view_only_base_when_no_layer():
    s = _new_store()
    base = [{"id": 1, "name": "alice"}]
    rows = s.view("ds.ri.no_layer", base, "id")
    assert rows == base


def test_view_uncommitted_layer_ignored():
    s = _new_store()
    txn = s.begin("ds.ri.1")
    s.apply(txn, [WritebackOp(op="upsert", pk="1", row={"name": "x"})])
    base = [{"id": 1, "name": "alice"}]
    rows = s.view("ds.ri.1", base, "id")
    assert rows[0]["name"] == "alice"


def test_view_bad_pk_field():
    s = _new_store()
    with pytest.raises(WritebackError) as exc:
        s.view("ds.ri.1", [], "")
    assert exc.value.code == "BAD_PK"


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = WritebackStore()
    monkeypatch.setattr("aos_api.routers.writeback.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_begin(client):
    resp = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H)
    assert resp.status_code == 200
    assert "txn_id" in resp.json()


def test_api_apply(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H).json()["txn_id"]
    resp = client.post(f"/v1/writeback/{txn}/apply", json={
        "ops": [{"op": "upsert", "pk": "1", "row": {"id": 1, "name": "alice"}}]
    }, headers=_H)
    assert resp.status_code == 200
    assert "1" in resp.json()["entries"]


def test_api_commit(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H).json()["txn_id"]
    resp = client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "committed"


def test_api_view(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H).json()["txn_id"]
    client.post(f"/v1/writeback/{txn}/apply", json={
        "ops": [{"op": "upsert", "pk": "2", "row": {"name": "new"}}]
    }, headers=_H)
    client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    resp = client.post("/v1/writeback/datasets/ds.1/view", json={
        "base_rows": [{"id": 1, "name": "a"}, {"id": 2, "name": "old"}],
        "pk_field": "id",
    }, headers=_H)
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()["rows"]}
    assert names == {"a", "new"}


def test_api_get_layer(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H).json()["txn_id"]
    resp = client.get("/v1/writeback/datasets/ds.1", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["dataset_rid"] == "ds.1"


def test_api_get_layer_404(client):
    resp = client.get("/v1/writeback/datasets/nope", headers=_H)
    assert resp.status_code == 404


def test_api_rollback(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H).json()["txn_id"]
    resp = client.post(f"/v1/writeback/{txn}/rollback", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rolled_back"


def test_api_commit_unknown_txn_404(client):
    resp = client.post("/v1/writeback/ghost/commit", headers=_H)
    assert resp.status_code == 404


def test_api_double_commit_400(client):
    txn = client.post("/v1/writeback/begin", json={"dataset_rid": "ds.1"}, headers=_H).json()["txn_id"]
    client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    resp = client.post(f"/v1/writeback/{txn}/commit", headers=_H)
    assert resp.status_code == 400
