"""W1-4 · Build 引擎 单元测试。

详见 docs/palantier/20_tech/220tech_build-engine.md §6。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.jobs.build_engine import BuildEngine, Job, JobSpec, JobStep
from aos_api.main import create_app


def _spec(**kw) -> JobSpec:
    base = dict(
        inputs=["ri.dataset.in1"],
        steps=[JobStep(name="filter", type="transform")],
        outputs=["ri.dataset.out1"],
        name="test-build",
    )
    base.update(kw)
    return JobSpec(**base)


# --------------------------------------------------------------------------- #
# 引擎核心
# --------------------------------------------------------------------------- #
def test_create_job_pending():
    eng = BuildEngine()
    job = eng.create_job(_spec())
    # 同步执行器：create 返回时已执行完，状态 SUCCEEDED
    assert job.id
    assert job.status in ("SUCCEEDED", "PENDING")


def test_job_lifecycle_success():
    eng = BuildEngine()
    job = eng.create_job(_spec())
    assert job.status == "SUCCEEDED"
    assert job.started_at is not None
    assert job.finished_at is not None
    assert any("成功完成" in e.message for e in job.logs)


def test_job_lifecycle_failure():
    eng = BuildEngine(sleeper=lambda _: None)
    job = eng.create_job(_spec(outputs=["ri.dataset.locked"]))
    # 强制制造锁定冲突：先锁住 locked 再创建第二个
    eng2 = BuildEngine(sleeper=lambda _: None)
    eng2._acquire_lock("ri.dataset.out1", "blocker")
    # 用 eng2 但 outputs 指向被锁的
    spec_locked = _spec(outputs=["ri.dataset.out1"])
    # 先在 eng2 上锁，再创建
    eng2._locks["ri.dataset.out1"] = "blocker-id"
    job2 = eng2.create_job(spec_locked)
    assert job2.status == "FAILED"
    assert job2.error is not None


def test_job_lifecycle_cancelled():
    eng = BuildEngine()
    job = Job(id="cancel-test", spec=_spec(), created_at="2026-01-01T00:00:00Z", status="RUNNING")
    eng._jobs[job.id] = job
    result = eng.cancel_job(job.id)
    assert result.status == "CANCELLED"


def test_transaction_lock_concurrent():
    eng = BuildEngine(sleeper=lambda _: None)
    eng._locks["ri.dataset.out1"] = "blocker-id"
    job = eng.create_job(_spec(outputs=["ri.dataset.out1"]))
    assert job.status == "FAILED"
    assert "锁定" in job.error


def test_lock_released_on_completion():
    eng = BuildEngine()
    job = eng.create_job(_spec(outputs=["ri.dataset.out1"]))
    assert job.status == "SUCCEEDED"
    assert not eng.is_locked("ri.dataset.out1")


def test_job_log_collection():
    eng = BuildEngine()
    job = eng.create_job(_spec(steps=[JobStep(name="s1"), JobStep(name="s2")]))
    timestamps = [e.timestamp for e in job.logs]
    assert timestamps == sorted(timestamps)
    assert any("s1" in e.message for e in job.logs)
    assert any("s2" in e.message for e in job.logs)


def test_jobspec_validation_no_inputs():
    eng = BuildEngine()
    with pytest.raises(Exception):
        eng.create_job(JobSpec(inputs=[], outputs=["ri.dataset.out1"]))


def test_jobspec_validation_no_outputs():
    eng = BuildEngine()
    with pytest.raises(Exception):
        eng.create_job(JobSpec(inputs=["ri.dataset.in1"], outputs=[]))


def test_job_retry_after_failure():
    eng = BuildEngine(sleeper=lambda _: None)
    eng._locks["ri.dataset.out1"] = "blocker-id"
    job = eng.create_job(_spec(outputs=["ri.dataset.out1"]))
    assert job.status == "FAILED"
    eng._release_lock("ri.dataset.out1")
    retried = eng.retry_job(job.id)
    assert retried.id != job.id
    assert retried.status == "SUCCEEDED"


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = BuildEngine()
    monkeypatch.setattr("aos_api.routers.builds.get_engine", lambda: fresh)
    return TestClient(create_app())


_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def test_create_build_endpoint(client):
    resp = client.post("/v1/builds", json={
        "inputs": ["ri.dataset.in1"],
        "steps": [{"name": "filter", "type": "transform"}],
        "outputs": ["ri.dataset.out1"],
        "name": "api-build",
    }, headers=_H)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCEEDED"
    assert body["id"]


def test_list_builds_endpoint(client):
    client.post("/v1/builds", json={"inputs": ["i1"], "outputs": ["o1"]}, headers=_H)
    resp = client.get("/v1/builds", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_build_detail_with_logs(client):
    r = client.post("/v1/builds", json={"inputs": ["i1"], "outputs": ["o1"]}, headers=_H)
    job_id = r.json()["id"]
    resp = client.get(f"/v1/builds/{job_id}", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["logs"]) > 0


def test_cancel_build_endpoint(client):
    import aos_api.routers.builds as br
    eng = br.get_engine()
    job = Job(id="run-1", spec=_spec(), created_at="2026-01-01T00:00:00Z", status="RUNNING")
    eng._jobs[job.id] = job
    resp = client.post("/v1/builds/run-1/cancel", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_build_not_found_404(client):
    resp = client.get("/v1/builds/nonexistent", headers=_H)
    assert resp.status_code == 404


def test_retry_build_endpoint(client):
    r = client.post("/v1/builds", json={"inputs": ["i1"], "outputs": ["o1"]}, headers=_H)
    job_id = r.json()["id"]
    resp = client.post(f"/v1/builds/{job_id}/retry", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["id"] != job_id
