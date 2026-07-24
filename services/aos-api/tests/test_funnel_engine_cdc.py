"""W2-#11 · Funnel 双管道 / CDC / 全量重索引 单元测试。

详见 docs/palantier/20_tech/220tech_w2-f-funnel-logic-writeback.md §2.1。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.funnel_engine import FunnelEngine, FunnelError
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-cdc",
}


def _stage(p, name):
    return next(s for s in p.stages if s.name == name)


# --------------------------------------------------------------------------- #
# CDC 行级 _op 识别
# --------------------------------------------------------------------------- #
def test_cdc_default_upsert_when_no_op():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [{"id": 1}, {"id": 2}])
    cl = _stage(p, "changelog")
    assert cl.op_counts == {"UPSERT": 2}


def test_cdc_respect_existing_op():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [
        {"id": 1, "_op": "UPDATE"},
        {"id": 2, "_op": "DELETE"},
    ])
    cl = _stage(p, "changelog")
    assert cl.op_counts == {"UPDATE": 1, "DELETE": 1}


def test_cdc_change_type_alias():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [{"id": 1, "_change_type": "delete"}])
    cl = _stage(p, "changelog")
    assert cl.op_counts == {"DELETE": 1}


def test_cdc_invalid_op_falls_back_upsert():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [{"id": 1, "_op": "WEIRD"}])
    cl = _stage(p, "changelog")
    assert cl.op_counts == {"UPSERT": 1}


def test_cdc_op_counts_mixed():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [
        {"id": 1},
        {"id": 2, "_op": "update"},
        {"id": 3, "_op": "DELETE"},
        {"id": 4, "_op": "UPSERT"},
    ])
    cl = _stage(p, "changelog")
    assert cl.op_counts == {"UPSERT": 2, "UPDATE": 1, "DELETE": 1}


# --------------------------------------------------------------------------- #
# 双管道 + DELETE 剔除
# --------------------------------------------------------------------------- #
def test_incremental_delete_removed_in_merge():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [
        {"id": 1, "name": "a"},
        {"id": 2, "_op": "DELETE", "name": "gone"},
        {"id": 3, "name": "c"},
    ], mode="incremental")
    merge = _stage(p, "merge")
    assert merge.output_count == 2  # id=2 被剔除
    assert any("剔除" in log for log in merge.logs)


def test_snapshot_mode_default():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [{"id": 1}])
    assert p.mode == "snapshot"


def test_incremental_sets_watermark():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [{"id": 1}], mode="incremental")
    assert p.mode == "incremental"
    assert p.watermark is not None


def test_snapshot_no_watermark():
    eng = FunnelEngine()
    p = eng.run("ds", "User", "id", [{"id": 1}], mode="snapshot")
    assert p.watermark is None


# --------------------------------------------------------------------------- #
# 全量重索引触发
# --------------------------------------------------------------------------- #
def test_reindex_resets_watermark():
    eng = FunnelEngine()
    eng.run("ds", "User", "id", [{"id": 1}], mode="incremental")
    rp = eng.reindex("ds", "User", "id", [{"id": 1}, {"id": 2}])
    assert rp.mode == "snapshot"
    assert rp.status == "SUCCEEDED"
    assert rp.watermark is None  # snapshot 不设水位


def test_reindex_clears_prior_incremental_watermark():
    eng = FunnelEngine()
    prior = eng.run("ds", "User", "id", [{"id": 1}], mode="incremental")
    assert prior.watermark is not None
    eng.reindex("ds", "User", "id", [{"id": 1}])
    assert prior.watermark is None  # 被重置


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = FunnelEngine()
    monkeypatch.setattr("aos_api.routers.funnel.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_run_incremental_mode(client):
    resp = client.post("/v1/funnel/run", json={
        "source_dataset": "ds",
        "target_object_type": "User",
        "primary_key": "id",
        "input_rows": [{"id": 1, "_op": "DELETE"}],
        "mode": "incremental",
    }, headers=_H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "incremental"
    assert body["watermark"] is not None


def test_api_reindex(client):
    resp = client.post("/v1/funnel/reindex", json={
        "source_dataset": "ds",
        "target_object_type": "User",
        "primary_key": "id",
        "input_rows": [{"id": 1}, {"id": 2}],
    }, headers=_H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "snapshot"
    assert body["status"] == "SUCCEEDED"
