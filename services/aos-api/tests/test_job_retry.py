"""W1-11 · Pipeline 重试机制 单元测试。

详见 docs/palantier/20_tech/220tech_pipeline-retry.md §7。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.jobs.build_engine import BuildEngine, JobSpec, JobStep
from aos_api.jobs.retry import DeadLetterQueue, RetryPolicy
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _spec(**kw) -> JobSpec:
    base = dict(
        inputs=["ri.dataset.in1"],
        steps=[JobStep(name="filter", type="transform")],
        outputs=["ri.dataset.out1"],
        name="retry-test-build",
    )
    base.update(kw)
    return JobSpec(**base)


def _failing_spec(fail_n: int = 10) -> JobSpec:
    return _spec(steps=[JobStep(
        name="flaky", type="transform", config={"_fail_n": fail_n},
    )])


# --------------------------------------------------------------------------- #
# RetryPolicy
# --------------------------------------------------------------------------- #
def test_policy_should_retry_within_limit():
    p = RetryPolicy(max_retries=3)
    assert p.should_retry(0) is True
    assert p.should_retry(1) is True
    assert p.should_retry(2) is True
    assert p.should_retry(3) is False


def test_policy_backoff_values():
    p = RetryPolicy(max_retries=3, base_delay=1.0)
    assert p.compute_backoff(0) == 1.0
    assert p.compute_backoff(1) == 2.0
    assert p.compute_backoff(2) == 4.0


# --------------------------------------------------------------------------- #
# 自动重试
# --------------------------------------------------------------------------- #
def test_auto_retry_on_failure():
    eng = BuildEngine(sleeper=lambda _: None)
    job = eng.create_job(_failing_spec(fail_n=10))
    assert job.status == "FAILED"
    assert job.retry_count == 3


def test_exponential_backoff():
    delays: list[float] = []
    eng = BuildEngine(sleeper=lambda d: delays.append(d))
    eng.create_job(_failing_spec(fail_n=10))
    assert delays == [1.0, 2.0, 4.0]


def test_max_retry_exceeded():
    eng = BuildEngine(sleeper=lambda _: None)
    job = eng.create_job(_failing_spec(fail_n=99))
    assert job.status == "FAILED"
    assert job.retry_count == 3
    assert eng.dlq.count() == 1


def test_retry_success_within_limit():
    eng = BuildEngine(sleeper=lambda _: None)
    job = eng.create_job(_failing_spec(fail_n=2))
    assert job.status == "SUCCEEDED"
    assert job.retry_count == 2
    assert job.retry_count <= job.max_retries


def test_no_retry_when_max_zero():
    import uuid
    from datetime import datetime, timezone
    from aos_api.jobs.build_engine import Job
    eng = BuildEngine(sleeper=lambda _: None)
    spec = _failing_spec(fail_n=1)
    job = Job(
        id=str(uuid.uuid4()), spec=spec,
        created_at=datetime.now(timezone.utc).isoformat(),
        max_retries=0,
    )
    eng._jobs[job.id] = job
    eng._execute(job)
    assert job.status == "FAILED"
    assert job.retry_count == 0
    assert eng.dlq.count() == 1


# --------------------------------------------------------------------------- #
# 手动重试
# --------------------------------------------------------------------------- #
def test_manual_retry():
    eng = BuildEngine(sleeper=lambda _: None)
    eng._locks["ri.dataset.out1"] = "blocker-id"
    job = eng.create_job(_spec(outputs=["ri.dataset.out1"]))
    assert job.status == "FAILED"
    eng._release_lock("ri.dataset.out1")
    retried = eng.retry_job(job.id)
    assert retried.id != job.id
    assert retried.status == "SUCCEEDED"
    assert retried.retry_count == 0


def test_retry_resets_count():
    eng = BuildEngine(sleeper=lambda _: None)
    job = eng.create_job(_failing_spec(fail_n=1))
    assert job.status == "SUCCEEDED"
    assert job.retry_count == 1
    retried = eng.retry_job(job.id)
    assert retried.retry_count == 0


# --------------------------------------------------------------------------- #
# 死信队列
# --------------------------------------------------------------------------- #
def test_dlq_on_max_retry():
    eng = BuildEngine(sleeper=lambda _: None)
    eng.create_job(_failing_spec(fail_n=99))
    assert eng.dlq.count() == 1
    entries = eng.dlq.list()
    assert entries[0].job_id is not None
    assert "模拟" in entries[0].error or "失败" in entries[0].error
    assert entries[0].retry_count == 3


def test_dlq_count():
    eng = BuildEngine(sleeper=lambda _: None)
    assert eng.dlq.count() == 0
    eng.create_job(_failing_spec(fail_n=99))
    eng.create_job(_failing_spec(fail_n=99))
    assert eng.dlq.count() == 2


def test_dlq_remove():
    eng = BuildEngine(sleeper=lambda _: None)
    eng.create_job(_failing_spec(fail_n=99))
    entries = eng.dlq.list()
    assert len(entries) == 1
    entry_id = entries[0].id
    assert eng.dlq.remove(entry_id) is True
    assert eng.dlq.count() == 0
    assert eng.dlq.remove(entry_id) is False


def test_dlq_get():
    eng = BuildEngine(sleeper=lambda _: None)
    eng.create_job(_failing_spec(fail_n=99))
    entries = eng.dlq.list()
    entry_id = entries[0].id
    got = eng.dlq.get(entry_id)
    assert got is not None
    assert got.id == entry_id
    assert eng.dlq.get("nonexistent") is None


def test_dlq_clear():
    eng = BuildEngine(sleeper=lambda _: None)
    eng.create_job(_failing_spec(fail_n=99))
    eng.create_job(_failing_spec(fail_n=99))
    assert eng.dlq.count() == 2
    removed = eng.dlq.clear()
    assert removed == 2
    assert eng.dlq.count() == 0


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = BuildEngine(sleeper=lambda _: None)
    monkeypatch.setattr("aos_api.routers.builds.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_dlq_visible(client):
    resp = client.post("/v1/builds", json={
        "inputs": ["ri.dataset.in1"],
        "steps": [{"name": "fail", "type": "transform", "config": {"_fail_n": 99}}],
        "outputs": ["ri.dataset.dlq-api"],
        "name": "dlq-api-build",
    }, headers=_H)
    assert resp.status_code == 200
    job_id = resp.json()["id"]
    assert resp.json()["status"] == "FAILED"

    resp = client.get("/v1/builds/dlq", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1
    items = resp.json()["items"]
    assert any(i["job_id"] == job_id for i in items)


def test_api_dlq_remove(client):
    client.post("/v1/builds", json={
        "inputs": ["i1"],
        "steps": [{"name": "f", "type": "transform", "config": {"_fail_n": 99}}],
        "outputs": ["ri.dataset.rm"],
        "name": "rm-build",
    }, headers=_H)
    resp = client.get("/v1/builds/dlq", headers=_H)
    entry_id = resp.json()["items"][0]["id"]

    resp = client.delete(f"/v1/builds/dlq/{entry_id}", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["removed"] is True

    resp = client.get("/v1/builds/dlq", headers=_H)
    assert resp.json()["count"] == 0


def test_api_dlq_not_found(client):
    resp = client.get("/v1/builds/dlq/nonexistent", headers=_H)
    assert resp.status_code == 404

    resp = client.delete("/v1/builds/dlq/nonexistent", headers=_H)
    assert resp.status_code == 404


def test_api_retry_count_in_response(client):
    resp = client.post("/v1/builds", json={
        "inputs": ["i1"],
        "steps": [{"name": "f", "type": "transform", "config": {"_fail_n": 99}}],
        "outputs": ["ri.dataset.rc"],
        "name": "rc-build",
    }, headers=_H)
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["retry_count"] == 3
    assert body["max_retries"] == 3


def test_api_manual_retry(client):
    resp = client.post("/v1/builds", json={
        "inputs": ["i1"],
        "steps": [{"name": "f", "type": "transform", "config": {"_fail_n": 4}}],
        "outputs": ["ri.dataset.mr"],
        "name": "mr-build",
    }, headers=_H)
    job_id = resp.json()["id"]
    assert resp.json()["status"] == "FAILED"

    resp = client.post(f"/v1/builds/{job_id}/retry", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCEEDED"
    assert resp.json()["retry_count"] == 0
