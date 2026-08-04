"""W2-8/9 · Dynamic Scheduling 引擎+数据模型 单元测试。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from aos_api.main import create_app
from aos_api.scheduling_engine import (
    Schedule,
    SchedulingEngine,
    SchedulingError,
    next_run_time,
    parse_cron_field,
)
from aos_api.tenant_scope import TenantScope
from fastapi.testclient import TestClient

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-w2-89",
}
SCOPE = TenantScope("dev-org", "dev-project")


# --------------------------------------------------------------------------- #
# cron 解析
# --------------------------------------------------------------------------- #
def test_parse_cron_star():
    assert parse_cron_field("*", 0, 59) == set(range(60))


def test_parse_cron_step():
    assert parse_cron_field("*/15", 0, 59) == {0, 15, 30, 45}


def test_parse_cron_range():
    assert parse_cron_field("9-17", 0, 23) == set(range(9, 18))


def test_parse_cron_list():
    assert parse_cron_field("0,30", 0, 59) == {0, 30}


def test_next_run_daily():
    cron = "0 9 * * *"
    after = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)
    nr = next_run_time(cron, after)
    assert nr.hour == 9
    assert nr.minute == 0


def test_next_run_every_15_min():
    cron = "*/15 * * * *"
    after = datetime(2026, 7, 22, 10, 7, tzinfo=timezone.utc)
    nr = next_run_time(cron, after)
    assert nr.minute == 15


def test_next_run_weekly():
    cron = "0 0 * * 1"
    after = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    nr = next_run_time(cron, after)
    assert nr.weekday() == 0


def test_invalid_cron():
    with pytest.raises(SchedulingError):
        next_run_time("invalid", None)


# --------------------------------------------------------------------------- #
# Schedule CRUD
# --------------------------------------------------------------------------- #
def test_create_and_get_schedule():
    eng = SchedulingEngine()
    sched = eng.create_schedule(SCOPE, Schedule(name="daily-build", cron="0 9 * * *"))
    assert sched.id
    assert sched.next_run_at is not None
    got = eng.get_schedule(SCOPE, sched.id)
    assert got is not None
    assert got.name == "daily-build"


def test_list_schedules():
    eng = SchedulingEngine()
    eng.create_schedule(SCOPE, Schedule(name="s1", cron="0 9 * * *", enabled=True))
    eng.create_schedule(SCOPE, Schedule(name="s2", cron="0 10 * * *", enabled=False))
    assert len(eng.list_schedules(SCOPE)) == 2
    assert len(eng.list_schedules(SCOPE, enabled_only=True)) == 1


def test_delete_schedule():
    eng = SchedulingEngine()
    sched = eng.create_schedule(SCOPE, Schedule(name="temp", cron="0 9 * * *"))
    assert eng.delete_schedule(SCOPE, sched.id) is True
    assert eng.delete_schedule(SCOPE, sched.id) is False


def test_update_schedule():
    eng = SchedulingEngine()
    sched = eng.create_schedule(SCOPE, Schedule(name="s", cron="0 9 * * *"))
    updated = eng.update_schedule(SCOPE, sched.id, name="updated", enabled=False)
    assert updated.name == "updated"
    assert updated.enabled is False


def test_update_cron_recalculates_next():
    eng = SchedulingEngine()
    sched = eng.create_schedule(SCOPE, Schedule(name="s", cron="0 9 * * *"))
    old_next = sched.next_run_at
    eng.update_schedule(SCOPE, sched.id, cron="0 10 * * *")
    assert sched.next_run_at != old_next


# --------------------------------------------------------------------------- #
# 资源分配
# --------------------------------------------------------------------------- #
def test_assign_and_get_resource():
    eng = SchedulingEngine()
    sched = eng.create_schedule(SCOPE, Schedule(name="s", cron="0 9 * * *"))
    from aos_api.scheduling_engine import ScheduledResource
    eng.assign_resource(SCOPE, ScheduledResource(
        schedule_id=sched.id, resource_type="dataset", resource_id="ri.dataset.orders",
    ))
    resources = eng.get_resources(SCOPE, sched.id)
    assert len(resources) == 1
    assert resources[0].resource_id == "ri.dataset.orders"


# --------------------------------------------------------------------------- #
# 执行与触发
# --------------------------------------------------------------------------- #
def test_trigger_success():
    calls = []
    eng = SchedulingEngine(executor=lambda s: calls.append(s.id))
    sched = eng.create_schedule(SCOPE, Schedule(name="s", cron="0 9 * * *"))
    exe = eng.trigger(SCOPE, sched.id)
    assert exe.status == "succeeded"
    assert len(calls) == 1
    assert sched.last_run_at is not None


def test_trigger_failure():
    def fail(s):
        raise RuntimeError("boom")
    eng = SchedulingEngine(executor=fail)
    sched = eng.create_schedule(SCOPE, Schedule(name="s", cron="0 9 * * *"))
    exe = eng.trigger(SCOPE, sched.id)
    assert exe.status == "failed"
    assert "boom" in (exe.error or "")


def test_history():
    eng = SchedulingEngine()
    sched = eng.create_schedule(SCOPE, Schedule(name="s", cron="0 9 * * *"))
    eng.trigger(SCOPE, sched.id)
    eng.trigger(SCOPE, sched.id)
    assert len(eng.history(SCOPE, sched.id)) == 2


def test_execute_due():
    eng = SchedulingEngine(executor=lambda s: None)
    eng.create_schedule(SCOPE, Schedule(name="every-min", cron="* * * * *"))
    results = eng.execute_due(SCOPE)
    assert len(results) == 1
    assert results[0].status == "succeeded"


def test_execute_due_skips_disabled():
    eng = SchedulingEngine(executor=lambda s: None)
    eng.create_schedule(SCOPE, Schedule(name="s", cron="* * * * *", enabled=False))
    results = eng.execute_due(SCOPE)
    assert len(results) == 0


def test_same_schedule_id_is_isolated_by_tenant_scope():
    eng = SchedulingEngine()
    other = TenantScope("other-org", "other-project")
    a = eng.create_schedule(
        SCOPE, Schedule(id="same-id", name="A", cron="0 9 * * *")
    )
    b = eng.create_schedule(
        other, Schedule(id="same-id", name="B", cron="0 9 * * *")
    )

    assert eng.get_schedule(SCOPE, "same-id") == a
    assert eng.get_schedule(other, "same-id") == b
    assert eng.list_schedules(SCOPE) == [a]
    assert eng.list_schedules(other) == [b]
    assert eng.delete_schedule(SCOPE, "same-id") is True
    assert eng.get_schedule(other, "same-id") == b


def test_schedule_scope_mismatch_is_rejected():
    eng = SchedulingEngine()
    with pytest.raises(SchedulingError) as mismatch:
        eng.create_schedule(
            SCOPE,
            Schedule(
                id="mismatch",
                name="bad",
                cron="0 9 * * *",
                org_id="other-org",
                project_id=SCOPE.project_id,
            ),
        )
    assert mismatch.value.code == "TENANT_SCOPE_MISMATCH"


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = SchedulingEngine(executor=lambda s: {"ok": True})
    monkeypatch.setattr("aos_api.routers.scheduling.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_create_schedule(client):
    resp = client.post("/v1/scheduling/schedules", json={
        "name": "api-test", "cron": "0 9 * * *",
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["next_run_at"] is not None


def test_api_trigger(client):
    create = client.post("/v1/scheduling/schedules", json={
        "name": "trigger-test", "cron": "0 9 * * *",
    }, headers=_H)
    sched_id = create.json()["id"]
    resp = client.post(f"/v1/scheduling/schedules/{sched_id}/trigger", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"


def test_api_next_run(client):
    create = client.post("/v1/scheduling/schedules", json={
        "name": "nr-test", "cron": "0 9 * * *",
    }, headers=_H)
    sched_id = create.json()["id"]
    resp = client.get(f"/v1/scheduling/schedules/{sched_id}/next-run", headers=_H)
    assert resp.status_code == 200
    assert "next_run_at" in resp.json()


def test_api_schedule_is_not_visible_in_another_scope(client):
    created = client.post(
        "/v1/scheduling/schedules",
        json={"name": "isolated", "cron": "0 9 * * *"},
        headers=_H,
    )
    assert created.status_code == 200
    sched_id = created.json()["id"]
    other_headers = {
        **_H,
        "X-Org-Id": "other-org",
        "X-Project-Id": "other-project",
    }
    hidden = client.get(
        f"/v1/scheduling/schedules/{sched_id}", headers=other_headers
    )
    assert hidden.status_code == 404
    assert client.get("/v1/scheduling/schedules", headers=other_headers).json() == {
        "items": []
    }
