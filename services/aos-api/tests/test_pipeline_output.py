"""W2-6 · Pipeline Builder 输出系统（6 种写入模式）单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.pipeline_output import OutputConfig, OutputTarget, PipelineOutputEngine

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-w2-6",
}


def _engine_with_seed():
    eng = PipelineOutputEngine()
    eng.seed_dataset("ri.dataset.orders", [
        {"id": 1, "name": "a", "status": "new"},
        {"id": 2, "name": "b", "status": "new"},
    ])
    return eng


def _target(eng, mode, pk="id"):
    return eng.register_target(OutputTarget(config=OutputConfig(
        target_dataset_rid="ri.dataset.orders",
        write_mode=mode, primary_key=pk,
    )))


# --------------------------------------------------------------------------- #
# 6 种写入模式
# --------------------------------------------------------------------------- #
def test_write_mode_append():
    eng = _engine_with_seed()
    t = _target(eng, "append")
    result = eng.execute(t.id, [{"id": 3, "name": "c", "status": "new"}])
    assert result.rows_after == 3
    assert result.rows_written == 1


def test_write_mode_replace():
    eng = _engine_with_seed()
    t = _target(eng, "replace")
    result = eng.execute(t.id, [{"id": 99, "name": "x", "status": "old"}])
    assert result.rows_after == 1
    assert result.rows_before == 2


def test_write_mode_snapshot():
    eng = _engine_with_seed()
    t = _target(eng, "snapshot")
    result = eng.execute(t.id, [{"id": 5, "name": "snap", "status": "new"}])
    assert result.snapshot_version is not None
    assert "v1-" in result.snapshot_version
    assert result.rows_after == 1


def test_write_mode_upsert():
    eng = _engine_with_seed()
    t = _target(eng, "upsert")
    result = eng.execute(t.id, [
        {"id": 1, "name": "a-updated", "status": "done"},
        {"id": 3, "name": "new", "status": "new"},
    ])
    assert result.rows_after == 3
    ds = eng.get_dataset("ri.dataset.orders")
    id1 = [r for r in ds if r["id"] == 1][0]
    assert id1["name"] == "a-updated"
    assert id1["status"] == "done"


def test_write_mode_update():
    eng = _engine_with_seed()
    t = _target(eng, "update")
    result = eng.execute(t.id, [{"id": 1, "status": "done"}])
    assert result.rows_written == 1
    assert result.rows_after == 2
    ds = eng.get_dataset("ri.dataset.orders")
    id1 = [r for r in ds if r["id"] == 1][0]
    assert id1["status"] == "done"
    assert id1["name"] == "a"


def test_write_mode_update_skip_nonexistent():
    eng = _engine_with_seed()
    t = _target(eng, "update")
    result = eng.execute(t.id, [{"id": 999, "status": "x"}])
    assert result.rows_written == 0
    assert result.rows_after == 2


def test_write_mode_delete():
    eng = _engine_with_seed()
    t = _target(eng, "delete")
    result = eng.execute(t.id, [{"id": 1}])
    assert result.rows_written == 1
    assert result.rows_after == 1
    ds = eng.get_dataset("ri.dataset.orders")
    assert all(r["id"] != 1 for r in ds)


def test_write_mode_delete_multiple():
    eng = _engine_with_seed()
    t = _target(eng, "delete")
    result = eng.execute(t.id, [{"id": 1}, {"id": 2}])
    assert result.rows_written == 2
    assert result.rows_after == 0


def test_write_mode_requires_pk():
    eng = _engine_with_seed()
    t = eng.register_target(OutputTarget(config=OutputConfig(
        target_dataset_rid="ri.dataset.orders", write_mode="upsert", primary_key="",
    )))
    with pytest.raises(Exception):
        eng.execute(t.id, [{"id": 1}])


def test_register_and_list_targets():
    eng = PipelineOutputEngine()
    eng.register_target(OutputTarget(config=OutputConfig(target_dataset_rid="ri.d1", write_mode="append")))
    eng.register_target(OutputTarget(config=OutputConfig(target_dataset_rid="ri.d2", write_mode="replace")))
    assert len(eng.list_targets()) == 2


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = _engine_with_seed()
    monkeypatch.setattr("aos_api.routers.pipeline_outputs.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_register_and_execute(client):
    resp = client.post("/v1/pipeline-outputs/targets", json={
        "target_dataset_rid": "ri.dataset.orders",
        "write_mode": "append",
    }, headers=_H)
    assert resp.status_code == 200
    target_id = resp.json()["id"]

    resp = client.post(f"/v1/pipeline-outputs/targets/{target_id}/execute", json={
        "input_rows": [{"id": 10, "name": "new-row"}],
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["rows_after"] == 3


def test_api_get_dataset(client):
    resp = client.get("/v1/pipeline-outputs/datasets/ri.dataset.orders", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["rows"]) == 2
