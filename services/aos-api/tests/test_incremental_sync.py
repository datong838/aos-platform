"""W2-23 · Data Connection 增量同步 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.incremental_sync import (
    IncrementalConfig,
    IncrementalSyncEngine,
    SyncConnection,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-w2-23",
}


def _engine_with_data():
    eng = IncrementalSyncEngine()
    eng.seed_source("ri.source.events", [
        {"id": 1, "name": "a", "updated_at": "2026-01-01T10:00:00Z"},
        {"id": 2, "name": "b", "updated_at": "2026-01-01T11:00:00Z"},
        {"id": 3, "name": "c", "updated_at": "2026-01-01T12:00:00Z"},
        {"id": 4, "name": "d", "updated_at": "2026-01-01T13:00:00Z"},
        {"id": 5, "name": "e", "updated_at": "2026-01-01T14:00:00Z"},
    ])
    return eng


def _conn(eng, **kw):
    base = dict(
        name="test-sync",
        source_dataset_rid="ri.source.events",
        target_dataset_rid="ri.target.events",
    )
    base.update(kw)
    conn = SyncConnection(
        name=base["name"],
        source_dataset_rid=base["source_dataset_rid"],
        target_dataset_rid=base["target_dataset_rid"],
        config=IncrementalConfig(
            incremental_column=base.get("incremental_column", "updated_at"),
            where_clause=base.get("where_clause", ""),
            batch_size=base.get("batch_size", 1000),
        ),
    )
    return eng.create_connection(conn)


# --------------------------------------------------------------------------- #
def test_initial_sync_all():
    eng = _engine_with_data()
    conn = _conn(eng)
    result = eng.sync(conn.id)
    assert result.rows_extracted == 5
    assert conn.state.total_synced == 5


def test_incremental_sync_only_new():
    eng = _engine_with_data()
    conn = _conn(eng)
    eng.sync(conn.id)
    eng.seed_source("ri.source.events", [
        {"id": 1, "name": "a", "updated_at": "2026-01-01T10:00:00Z"},
        {"id": 6, "name": "f", "updated_at": "2026-01-01T15:00:00Z"},
    ])
    result = eng.sync(conn.id)
    assert result.rows_extracted == 1
    assert conn.state.total_synced == 6


def test_where_clause_filter():
    eng = _engine_with_data()
    conn = _conn(eng, where_clause="id >= 3")
    result = eng.sync(conn.id)
    assert result.rows_extracted == 3


def test_batch_size_limit():
    eng = _engine_with_data()
    conn = _conn(eng, batch_size=2)
    result = eng.sync(conn.id)
    assert result.rows_extracted == 2
    assert conn.state.total_synced == 2


def test_reset_state():
    eng = _engine_with_data()
    conn = _conn(eng)
    eng.sync(conn.id)
    assert conn.state.total_synced == 5
    eng.reset_state(conn.id)
    assert conn.state.total_synced == 0
    assert conn.state.last_synced_value is None


def test_numeric_incremental_column():
    eng = IncrementalSyncEngine()
    eng.seed_source("ri.src", [
        {"id": 10, "val": "a"},
        {"id": 20, "val": "b"},
        {"id": 30, "val": "c"},
    ])
    conn = SyncConnection(
        name="num", source_dataset_rid="ri.src", target_dataset_rid="ri.tgt",
        config=IncrementalConfig(incremental_column="id"),
    )
    eng.create_connection(conn)
    result = eng.sync(conn.id)
    assert result.rows_extracted == 3
    result2 = eng.sync(conn.id)
    assert result2.rows_extracted == 0


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = _engine_with_data()
    monkeypatch.setattr("aos_api.routers.incremental_sync.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_create_and_sync(client):
    resp = client.post("/v1/incremental-sync/connections", json={
        "name": "api-sync",
        "source_dataset_rid": "ri.source.events",
        "target_dataset_rid": "ri.target.events",
        "incremental_column": "updated_at",
    }, headers=_H)
    assert resp.status_code == 200
    conn_id = resp.json()["id"]

    resp = client.post(f"/v1/incremental-sync/connections/{conn_id}/sync", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["rows_extracted"] == 5
