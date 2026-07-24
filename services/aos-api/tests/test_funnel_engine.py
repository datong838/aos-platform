"""W1-5 · Funnel 四阶段管道 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.funnel_engine import FunnelEngine, FunnelError
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}

_ROWS = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 1, "name": "Alice2"},
    {"id": 3, "name": "Carol"},
]


def test_funnel_four_stages():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", _ROWS)
    assert p.status == "SUCCEEDED"
    assert len(p.stages) == 4
    assert all(s.status == "SUCCEEDED" for s in p.stages)


def test_funnel_changelog_adds_op():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", _ROWS)
    changelog = next(s for s in p.stages if s.name == "changelog")
    assert changelog.input_count == 4
    assert changelog.output_count == 4


def test_funnel_merge_dedup():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", _ROWS)
    merge = next(s for s in p.stages if s.name == "merge")
    assert merge.input_count == 4
    assert merge.output_count == 3  # id=1 去重


def test_funnel_indexing_sorted():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", [{"id": 3}, {"id": 1}, {"id": 2}])
    indexing = next(s for s in p.stages if s.name == "indexing")
    assert indexing.output_count == 3


def test_funnel_hydration_object_type():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "Order", "id", [{"id": 1}])
    hydration = next(s for s in p.stages if s.name == "hydration")
    assert hydration.status == "SUCCEEDED"


def test_funnel_empty_rows():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", [])
    assert p.status == "SUCCEEDED"
    assert all(s.output_count == 0 for s in p.stages)


def test_funnel_invalid_no_source():
    eng = FunnelEngine()
    with pytest.raises(FunnelError) as exc:
        eng.run("", "User", "id", [])
    assert exc.value.code == "INVALID_INPUT"


def test_funnel_invalid_no_pk():
    eng = FunnelEngine()
    with pytest.raises(FunnelError) as exc:
        eng.run("ri.ds.src", "User", "", [])
    assert exc.value.code == "INVALID_INPUT"


def test_funnel_get_pipeline():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", _ROWS)
    found = eng.get_pipeline(p.id)
    assert found is not None
    assert found.status == "SUCCEEDED"


def test_funnel_get_stage():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", _ROWS)
    stage = eng.get_stage(p.id, "merge")
    assert stage.name == "merge"
    assert stage.status == "SUCCEEDED"


def test_funnel_get_stage_not_found():
    eng = FunnelEngine()
    p = eng.run("ri.ds.src", "User", "id", _ROWS)
    with pytest.raises(FunnelError):
        eng.get_stage(p.id, "nonexistent")


# --- API --- #
@pytest.fixture()
def client(monkeypatch):
    from aos_api.funnel_engine import FunnelEngine as FE
    fresh = FE()
    monkeypatch.setattr("aos_api.routers.funnel.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_run_funnel(client):
    resp = client.post("/v1/funnel/run", json={
        "source_dataset": "ri.ds.src",
        "target_object_type": "User",
        "primary_key": "id",
        "input_rows": [{"id": 1, "name": "A"}],
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCEEDED"


def test_api_list_funnels(client):
    client.post("/v1/funnel/run", json={"source_dataset": "x", "primary_key": "id"}, headers=_H)
    resp = client.get("/v1/funnel", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_api_get_funnel(client):
    r = client.post("/v1/funnel/run", json={"source_dataset": "x", "primary_key": "id"}, headers=_H)
    pid = r.json()["id"]
    resp = client.get(f"/v1/funnel/{pid}", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["stages"]) == 4


def test_api_get_stage(client):
    r = client.post("/v1/funnel/run", json={"source_dataset": "x", "primary_key": "id"}, headers=_H)
    pid = r.json()["id"]
    resp = client.get(f"/v1/funnel/{pid}/stage/merge", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["name"] == "merge"


def test_api_funnel_not_found_404(client):
    resp = client.get("/v1/funnel/nonexistent", headers=_H)
    assert resp.status_code == 404
