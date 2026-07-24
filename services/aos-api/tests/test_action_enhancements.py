"""W2-#54/#55/#56/#57/#76 · Action 增强组 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.action_enhancements import (
    ActionEffect,
    ActionEnhancementEngine,
    EffectType,
    MergeStrategy,
    get_engine,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-act",
}


# ── #54 Side Effects ──
def test_create_effect():
    eng = ActionEnhancementEngine()
    eff = eng.create_effect(ActionEffect(
        action_type_id="act-1", type=EffectType.NOTIFICATION,
        config={"recipients": ["user1"], "template": "hello"},
    ))
    assert eff.id.startswith("eff-")
    assert eff.type == EffectType.NOTIFICATION


def test_trigger_notification():
    eng = ActionEnhancementEngine()
    eff = eng.create_effect(ActionEffect(
        action_type_id="act-1", type=EffectType.NOTIFICATION,
        config={"recipients": ["a", "b"], "template": "msg"},
    ))
    result = eng.trigger_effect(eff.id, {"data": "test"})
    assert result.status == "success"
    assert len(eng._notification_log) == 1


def test_trigger_webhook():
    eng = ActionEnhancementEngine()
    eff = eng.create_effect(ActionEffect(
        action_type_id="act-1", type=EffectType.WEBHOOK,
        config={"url": "http://example.com", "method": "POST"},
    ))
    result = eng.trigger_effect(eff.id, {"event": "created"})
    assert result.status == "success"
    assert len(eng._webhook_log) == 1


def test_effect_disabled():
    eng = ActionEnhancementEngine()
    eff = eng.create_effect(ActionEffect(
        action_type_id="act-1", type=EffectType.NOTIFICATION, enabled=False,
    ))
    result = eng.trigger_effect(eff.id, {})
    assert result.status == "pending"


# ── #55 Optimistic UI ──
def test_optimistic_submit_commit():
    eng = ActionEnhancementEngine()
    submit = eng.optimistic_submit("act-1", {"field": "value"})
    assert submit.ok is True
    commit = eng.optimistic_commit(submit.token)
    assert commit.ok is True


def test_optimistic_rollback():
    eng = ActionEnhancementEngine()
    submit = eng.optimistic_submit("act-1", {"field": "value"})
    rollback = eng.optimistic_rollback(submit.token)
    assert rollback.rollback_required is True
    assert rollback.rollback_payload == {"field": "value"}


def test_optimistic_token_not_found():
    eng = ActionEnhancementEngine()
    with pytest.raises(Exception):
        eng.optimistic_commit("ghost-token")


# ── #56 Soft Delete ──
def test_soft_delete():
    eng = ActionEnhancementEngine()
    result = eng.soft_delete("ds.soft", "pk-1")
    assert result["deleted"] is True
    assert "txn_id" in result


def test_undelete():
    from aos_api.writeback import WritebackOp, get_store

    store = get_store()
    txn_id = store.begin("ds.undel")
    store.apply(txn_id, [WritebackOp(op="soft_delete", pk="pk-2")])
    store.apply(txn_id, [WritebackOp(op="undelete", pk="pk-2")])
    store.commit(txn_id)
    layer = store.get_layer("ds.undel")
    assert layer is not None
    entry = layer.entries.get("pk-2")
    assert entry is not None
    assert entry.deleted is False


# ── #57 DLQ ──
def test_effect_retry_then_dlq():
    eng = ActionEnhancementEngine()

    def fail_execute(self, effect, payload):
        raise RuntimeError("always fail")

    original = eng._execute_notification
    eng._execute_notification = fail_execute.__get__(eng, ActionEnhancementEngine)
    try:
        eff = eng.create_effect(ActionEffect(
            action_type_id="act-1", type=EffectType.NOTIFICATION, retry=2,
        ))
        result = eng.trigger_effect(eff.id, {})
        assert result.status == "dlq"
        assert result.attempt == 2
        assert len(eng.list_dlq()) == 1
    finally:
        eng._execute_notification = original


def test_dlq_retry_success():
    eng = ActionEnhancementEngine()
    eff = eng.create_effect(ActionEffect(
        action_type_id="act-1", type=EffectType.NOTIFICATION,
    ))
    eng._dlq[eff.id] = type("DLQEntry", (), {
        "effect_id": eff.id,
        "action_type_id": "act-1",
        "payload": {},
        "attempts": 0,
        "max_attempts": 3,
        "last_error": "",
    })()
    result = eng.retry_dlq(eff.id)
    assert result.status == "success"
    assert len(eng.list_dlq()) == 0


def test_clear_dlq():
    eng = ActionEnhancementEngine()
    eng._dlq["dlq-1"] = type("DLQEntry", (), {})()
    eng._dlq["dlq-2"] = type("DLQEntry", (), {})()
    cleared = eng.clear_dlq()
    assert cleared == 2
    assert len(eng.list_dlq()) == 0


# ── #76 Merge Strategy ──
def test_merge_field_level():
    eng = ActionEnhancementEngine()
    result = eng.merge(
        {"a": 1, "b": 2},
        {"b": 20, "c": 3},
        MergeStrategy.FIELD_LEVEL,
    )
    assert result.merged == {"a": 1, "b": 20, "c": 3}
    assert len(result.conflicts) == 0


def test_merge_last_write_wins():
    eng = ActionEnhancementEngine()
    result = eng.merge(
        {"a": 1, "b": 2},
        {"b": 20, "c": 3},
        MergeStrategy.LAST_WRITE_WINS,
    )
    assert result.merged == {"b": 20, "c": 3}


def test_merge_manual_arbitration_with_conflicts():
    eng = ActionEnhancementEngine()
    result = eng.merge(
        {"a": 1, "b": 2},
        {"a": 10, "b": 2},
        MergeStrategy.MANUAL_ARBITRATION,
    )
    assert len(result.conflicts) == 1
    assert result.conflicts[0].field == "a"
    assert result.conflicts[0].current_value == 1
    assert result.conflicts[0].incoming_value == 10


def test_merge_manual_arbitration_no_conflicts():
    eng = ActionEnhancementEngine()
    result = eng.merge(
        {"a": 1, "b": 2},
        {"a": 1, "c": 3},
        MergeStrategy.MANUAL_ARBITRATION,
    )
    assert len(result.conflicts) == 0


def test_merge_unknown_strategy():
    eng = ActionEnhancementEngine()
    with pytest.raises(Exception):
        eng.merge({}, {}, "unknown")


# ── API ──
@pytest.fixture()
def client(monkeypatch):
    fresh = ActionEnhancementEngine()
    monkeypatch.setattr("aos_api.routers.action_enhancements.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_effects(client):
    create = client.post("/v1/actions/effects", json={
        "action_type_id": "act-api",
        "type": "notification",
        "config": {"recipients": ["u1"]},
    }, headers=_H)
    assert create.status_code == 200
    eid = create.json()["id"]
    trigger = client.post(f"/v1/actions/effects/{eid}/trigger", json={"payload": {"x": 1}}, headers=_H)
    assert trigger.status_code == 200
    assert trigger.json()["status"] == "success"


def test_api_optimistic(client):
    submit = client.post("/v1/actions/optimistic", json={
        "action_type_id": "act-opt",
        "payload": {"f": "v"},
    }, headers=_H)
    assert submit.status_code == 200
    token = submit.json()["token"]
    commit = client.post(f"/v1/actions/optimistic/{token}/commit", headers=_H)
    assert commit.status_code == 200


def test_api_soft_delete(client):
    resp = client.post("/v1/actions/soft-delete", json={
        "dataset_rid": "ds.api-del",
        "pk": "pk-api",
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_api_merge(client):
    resp = client.post("/v1/actions/merge", json={
        "current": {"a": 1, "b": 2},
        "incoming": {"b": 20, "c": 3},
        "strategy": "field_level",
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["merged"]["b"] == 20


def test_api_dlq(client):
    resp = client.get("/v1/actions/dlq", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 0
