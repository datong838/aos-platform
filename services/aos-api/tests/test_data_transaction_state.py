"""W2-#16 / W2-#17 · WriteMode 增强 + Transaction 状态机 单元测试。

详见 docs/palantier/20_tech/220tech_w2-g-expectation-writemode-txn.md §2.2/§2.3。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.data_transaction import (
    ALL_WRITE_MODES,
    TransactionError,
    TransactionStatus,
    TransactionStore,
    WRITE_MODE_DEFAULT,
    apply_write_mode,
    resolve_write_mode,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-txn",
}


# --------------------------------------------------------------------------- #
# WriteMode 增强（W2-#16）
# --------------------------------------------------------------------------- #
def test_resolve_default_mode():
    assert resolve_write_mode(None) == WRITE_MODE_DEFAULT


def test_default_in_all_modes():
    assert WRITE_MODE_DEFAULT in ALL_WRITE_MODES
    assert len(ALL_WRITE_MODES) == 4


def test_apply_default_equals_append():
    existing = [{"id": 1, "v": "a"}]
    new = [{"id": 2, "v": "b"}]
    result_default = apply_write_mode(existing, new, "default")
    result_append = apply_write_mode(existing, new, "append")
    assert result_default == result_append


def test_apply_default_with_none():
    existing = [{"id": 1}]
    new = [{"id": 2}]
    result = apply_write_mode(existing, new, None)
    assert len(result) == 2


# --------------------------------------------------------------------------- #
# Transaction 状态机（W2-#17）
# --------------------------------------------------------------------------- #
def test_txn_begin_open():
    store = TransactionStore()
    txn = store.begin("ds.1")
    assert txn.status == TransactionStatus.OPEN
    assert txn.dataset_rid == "ds.1"
    assert txn.write_mode == WRITE_MODE_DEFAULT


def test_txn_write_stages_rows():
    store = TransactionStore()
    txn = store.begin("ds.1")
    store.write(txn.id, [{"id": 1}, {"id": 2}])
    assert len(txn.staged_rows) == 2


def test_txn_commit_applies_write_mode():
    store = TransactionStore()
    store.seed_dataset("ds.1", [{"id": 1, "v": "a"}])
    txn = store.begin("ds.1", write_mode="append")
    store.write(txn.id, [{"id": 2, "v": "b"}])
    committed = store.commit(txn.id)
    assert committed.status == TransactionStatus.COMMITTED
    assert committed.committed_at is not None
    dataset = store.get_dataset("ds.1")
    assert len(dataset) == 2  # 1 existing + 1 new


def test_txn_commit_snapshot_replaces():
    store = TransactionStore()
    store.seed_dataset("ds.1", [{"id": 1}, {"id": 2}, {"id": 3}])
    txn = store.begin("ds.1", write_mode="snapshot")
    store.write(txn.id, [{"id": 10}])
    committed = store.commit(txn.id)
    assert committed.status == TransactionStatus.COMMITTED
    dataset = store.get_dataset("ds.1")
    assert len(dataset) == 1
    assert dataset[0]["id"] == 10


def test_txn_abort_discards_staged():
    store = TransactionStore()
    store.seed_dataset("ds.1", [{"id": 1}])
    txn = store.begin("ds.1")
    store.write(txn.id, [{"id": 2}])
    aborted = store.abort(txn.id)
    assert aborted.status == TransactionStatus.ABORTED
    assert aborted.aborted_at is not None
    assert len(aborted.staged_rows) == 0
    dataset = store.get_dataset("ds.1")
    assert len(dataset) == 1  # 存量不变


def test_txn_commit_not_reversible():
    store = TransactionStore()
    txn = store.begin("ds.1")
    store.commit(txn.id)
    with pytest.raises(TransactionError) as exc:
        store.commit(txn.id)
    assert exc.value.code == "TXN_NOT_OPEN"


def test_txn_abort_not_reversible():
    store = TransactionStore()
    txn = store.begin("ds.1")
    store.abort(txn.id)
    with pytest.raises(TransactionError) as exc:
        store.abort(txn.id)
    assert exc.value.code == "TXN_NOT_OPEN"


def test_txn_write_after_commit_fails():
    store = TransactionStore()
    txn = store.begin("ds.1")
    store.commit(txn.id)
    with pytest.raises(TransactionError) as exc:
        store.write(txn.id, [{"id": 1}])
    assert exc.value.code == "TXN_NOT_OPEN"


def test_txn_not_found():
    store = TransactionStore()
    with pytest.raises(TransactionError) as exc:
        store.commit("ghost")
    assert exc.value.code == "NOT_FOUND"


def test_txn_list_by_dataset():
    store = TransactionStore()
    store.begin("ds.1")
    store.begin("ds.1")
    store.begin("ds.2")
    assert len(store.list("ds.1")) == 2
    assert len(store.list("ds.2")) == 1
    assert len(store.list()) == 3


def test_txn_with_expectation_ids():
    store = TransactionStore()
    txn = store.begin("ds.1", expectation_ids=["exp-1", "exp-2"])
    assert txn.expectation_ids == ["exp-1", "exp-2"]


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = TransactionStore()
    monkeypatch.setattr("aos_api.routers.data_transaction.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_write_modes(client):
    resp = client.get("/v1/data-transactions/write-modes", headers=_H)
    assert resp.status_code == 200
    modes = resp.json()["modes"]
    assert len(modes) == 4
    assert any(m["mode"] == "default" for m in modes)


def test_api_begin_write_commit(client):
    begin = client.post("/v1/data-transactions/begin", json={
        "dataset_rid": "ds.api", "write_mode": "append",
    }, headers=_H)
    assert begin.status_code == 200
    txn_id = begin.json()["id"]
    assert begin.json()["status"] == "open"

    write = client.post(f"/v1/data-transactions/{txn_id}/write", json={
        "rows": [{"id": 1}, {"id": 2}],
    }, headers=_H)
    assert write.status_code == 200
    assert len(write.json()["staged_rows"]) == 2

    commit = client.post(f"/v1/data-transactions/{txn_id}/commit", headers=_H)
    assert commit.status_code == 200
    assert commit.json()["status"] == "committed"


def test_api_abort(client):
    begin = client.post("/v1/data-transactions/begin", json={
        "dataset_rid": "ds.api2",
    }, headers=_H)
    txn_id = begin.json()["id"]
    abort = client.post(f"/v1/data-transactions/{txn_id}/abort", headers=_H)
    assert abort.status_code == 200
    assert abort.json()["status"] == "aborted"


def test_api_get_and_list(client):
    begin = client.post("/v1/data-transactions/begin", json={
        "dataset_rid": "ds.list",
    }, headers=_H)
    txn_id = begin.json()["id"]

    get = client.get(f"/v1/data-transactions/{txn_id}", headers=_H)
    assert get.status_code == 200

    lst = client.get("/v1/data-transactions?dataset_rid=ds.list", headers=_H)
    assert lst.status_code == 200
    assert len(lst.json()["transactions"]) == 1


def test_api_commit_twice_400(client):
    begin = client.post("/v1/data-transactions/begin", json={
        "dataset_rid": "ds.twice",
    }, headers=_H)
    txn_id = begin.json()["id"]
    client.post(f"/v1/data-transactions/{txn_id}/commit", headers=_H)
    second = client.post(f"/v1/data-transactions/{txn_id}/commit", headers=_H)
    assert second.status_code == 400


def test_api_not_found_404(client):
    resp = client.get("/v1/data-transactions/ghost", headers=_H)
    assert resp.status_code == 404
