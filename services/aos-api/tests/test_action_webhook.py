"""W2-R · Action Webhook/Sections/Revert 测试：#64 Webhook 副作用 + #65 Section 分组 + #66 Revert 撤销."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aos_api.action_webhook import (
    ActionSection,
    RevertEngine,
    RevertError,
    RevertRule,
    SectionEngine,
    SectionError,
    SectionField,
    WebhookEngine,
    WebhookError,
    WebhookSideEffect,
)


# ── #64 Action Webhook 副作用 ──

def test_webhook_create():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(
        action_id="a1", name="notify", url="https://example.com/hook",
    ))
    assert e.id.startswith("wh-")
    assert e.mode == "data_output"
    assert e.method == "POST"


def test_webhook_get_not_found():
    eng = WebhookEngine()
    with pytest.raises(WebhookError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_webhook_list_filter_by_action():
    eng = WebhookEngine()
    eng.create(WebhookSideEffect(action_id="a1", name="n1", url="https://x"))
    eng.create(WebhookSideEffect(action_id="a2", name="n2", url="https://y"))
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list()) == 2


def test_webhook_update():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(action_id="a", name="n", url="https://x"))
    updated = eng.update(e.id, {"name": "renamed", "method": "put"})
    assert updated.name == "renamed"
    assert updated.method == "PUT"


def test_webhook_delete():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(action_id="a", name="n", url="https://x"))
    assert eng.delete(e.id) is True
    with pytest.raises(WebhookError):
        eng.get(e.id)


def test_webhook_invalid_mode():
    eng = WebhookEngine()
    with pytest.raises(WebhookError) as exc:
        eng.create(WebhookSideEffect(
            action_id="a", name="n", url="https://x", mode="invalid",
        ))
    assert exc.value.code == "INVALID_MODE"


def test_webhook_invalid_method():
    eng = WebhookEngine()
    with pytest.raises(WebhookError) as exc:
        eng.create(WebhookSideEffect(
            action_id="a", name="n", url="https://x", method="DELETE",
        ))
    assert exc.value.code == "INVALID_METHOD"


def test_webhook_invalid_auth():
    eng = WebhookEngine()
    with pytest.raises(WebhookError) as exc:
        eng.create(WebhookSideEffect(
            action_id="a", name="n", url="https://x", auth_type="oauth",
        ))
    assert exc.value.code == "INVALID_AUTH"


def test_webhook_build_request_template():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(
        action_id="a", name="n", url="https://x.com/{{path}}",
        input_mapping={"target_id": "{{obj_id}}", "static": "fixed"},
    ))
    req = eng.build_request(e.id, {"path": "users", "obj_id": "u-123"})
    assert req["url"] == "https://x.com/users"
    assert req["payload"]["target_id"] == "u-123"
    assert req["payload"]["static"] == "fixed"


def test_webhook_build_request_bearer_auth():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(
        action_id="a", name="n", url="https://x",
        auth_type="bearer", auth_config={"token": "tk-xyz"},
    ))
    req = eng.build_request(e.id, {})
    assert req["headers"]["Authorization"] == "Bearer tk-xyz"


def test_webhook_build_request_basic_auth():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(
        action_id="a", name="n", url="https://x",
        auth_type="basic", auth_config={"username": "u", "password": "p"},
    ))
    req = eng.build_request(e.id, {})
    assert req["headers"]["Authorization"].startswith("Basic ")


def test_webhook_apply_response():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(
        action_id="a", name="n", url="https://x",
        mode="data_output",
        output_mapping={"output_id": "data.result.id", "output_name": "data.name"},
    ))
    resp = {"data": {"result": {"id": "r-1"}, "name": "Alice"}}
    out = eng.apply_response(e.id, resp)
    assert out["output_id"] == "r-1"
    assert out["output_name"] == "Alice"


def test_webhook_apply_response_not_data_output_mode():
    eng = WebhookEngine()
    e = eng.create(WebhookSideEffect(
        action_id="a", name="n", url="https://x", mode="side_effect",
        output_mapping={"o": "data"},
    ))
    with pytest.raises(WebhookError) as exc:
        eng.apply_response(e.id, {"data": 1})
    assert exc.value.code == "NOT_DATA_OUTPUT_MODE"


# ── #65 Action Sections 分组 ──

def test_section_create():
    eng = SectionEngine()
    s = eng.create(ActionSection(
        action_id="a1", name="basic", fields=[SectionField(param_name="p1")],
    ))
    assert s.id.startswith("sec-")
    assert s.layout == "single_column"
    assert len(s.fields) == 1


def test_section_get_not_found():
    eng = SectionEngine()
    with pytest.raises(SectionError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_section_list_sorted_by_order():
    eng = SectionEngine()
    s1 = eng.create(ActionSection(action_id="a", name="b", order=2))
    s2 = eng.create(ActionSection(action_id="a", name="a", order=1))
    items = eng.list(action_id="a")
    assert items[0].id == s2.id
    assert items[1].id == s1.id


def test_section_update():
    eng = SectionEngine()
    s = eng.create(ActionSection(action_id="a", name="n"))
    updated = eng.update(s.id, {"name": "renamed", "collapsed": True})
    assert updated.name == "renamed"
    assert updated.collapsed is True


def test_section_delete():
    eng = SectionEngine()
    s = eng.create(ActionSection(action_id="a", name="n"))
    assert eng.delete(s.id) is True
    with pytest.raises(SectionError):
        eng.get(s.id)


def test_section_invalid_layout():
    eng = SectionEngine()
    with pytest.raises(SectionError) as exc:
        eng.create(ActionSection(action_id="a", name="n", layout="triple"))
    assert exc.value.code == "INVALID_LAYOUT"


def test_section_visibility_no_condition():
    eng = SectionEngine()
    s = eng.create(ActionSection(action_id="a", name="n"))
    result = eng.evaluate_visibility(s.id, {})
    assert result["visible"] is True


def test_section_visibility_eq_condition():
    eng = SectionEngine()
    s = eng.create(ActionSection(
        action_id="a", name="n", visible_condition="status = 'draft'",
    ))
    assert eng.evaluate_visibility(s.id, {"status": "draft"})["visible"] is True
    assert eng.evaluate_visibility(s.id, {"status": "published"})["visible"] is False


def test_section_visibility_numeric_condition():
    eng = SectionEngine()
    s = eng.create(ActionSection(
        action_id="a", name="n", visible_condition="level > 5",
    ))
    assert eng.evaluate_visibility(s.id, {"level": 10})["visible"] is True
    assert eng.evaluate_visibility(s.id, {"level": 3})["visible"] is False


def test_section_reorder():
    eng = SectionEngine()
    s1 = eng.create(ActionSection(action_id="a", name="a", order=0))
    s2 = eng.create(ActionSection(action_id="a", name="b", order=1))
    s3 = eng.create(ActionSection(action_id="a", name="c", order=2))
    items = eng.reorder("a", [s3.id, s1.id, s2.id])
    assert items[0].id == s3.id
    assert items[0].order == 0
    assert items[1].id == s1.id
    assert items[1].order == 1


def test_section_reorder_ignores_other_actions():
    eng = SectionEngine()
    s1 = eng.create(ActionSection(action_id="a", name="a", order=0))
    s_other = eng.create(ActionSection(action_id="b", name="b", order=5))
    items = eng.reorder("a", [s_other.id, s1.id])
    # s_other 属于 action b，不应被重排
    assert s_other.order == 5
    assert s1.order == 1


def test_section_double_column_with_span():
    eng = SectionEngine()
    s = eng.create(ActionSection(
        action_id="a", name="n", layout="double_column",
        fields=[
            SectionField(param_name="half1", span=1),
            SectionField(param_name="full1", span=2),
        ],
    ))
    fetched = eng.get(s.id)
    assert fetched.layout == "double_column"
    assert fetched.fields[0].span == 1
    assert fetched.fields[1].span == 2


def test_section_update_fields():
    eng = SectionEngine()
    s = eng.create(ActionSection(action_id="a", name="n"))
    updated = eng.update(s.id, {
        "fields": [{"param_name": "new_p", "span": 2}],
    })
    assert len(updated.fields) == 1
    assert updated.fields[0].param_name == "new_p"


# ── #66 Action 撤销（Revert） ──

def test_revert_rule_create():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a1", name="undo"))
    assert r.id.startswith("rr-")
    assert r.requires_confirmation is True


def test_revert_rule_get_not_found():
    eng = RevertEngine()
    with pytest.raises(RevertError) as exc:
        eng.get_rule("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_revert_rule_list_filter():
    eng = RevertEngine()
    eng.create_rule(RevertRule(action_id="a1", name="r1"))
    eng.create_rule(RevertRule(action_id="a2", name="r2"))
    assert len(eng.list_rules(action_id="a1")) == 1
    assert len(eng.list_rules()) == 2


def test_revert_rule_update():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    updated = eng.update_rule(r.id, {"name": "renamed", "revert_window_seconds": 60})
    assert updated.name == "renamed"
    assert updated.revert_window_seconds == 60


def test_revert_rule_delete():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    assert eng.delete_rule(r.id) is True
    with pytest.raises(RevertError):
        eng.get_rule(r.id)


def test_revert_check_no_window_no_condition():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    result = eng.check(r.id, {})
    assert result["eligible"] is True


def test_revert_check_window_passed():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(
        action_id="a", name="n", revert_window_seconds=60,
    ))
    # 提交时间在 2 分钟前，已超过 60 秒窗口
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    result = eng.check(r.id, {"submitted_at": old_time})
    assert result["eligible"] is False
    assert "撤销窗口已过" in result["reason"]


def test_revert_check_window_not_passed():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(
        action_id="a", name="n", revert_window_seconds=3600,
    ))
    recent = datetime.now(timezone.utc).isoformat()
    result = eng.check(r.id, {"submitted_at": recent})
    assert result["eligible"] is True


def test_revert_check_pre_condition_failed():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(
        action_id="a", name="n",
        pre_revert_check={"op": "=", "field": "status", "value": "pending"},
    ))
    result = eng.check(r.id, {"status": "completed"})
    assert result["eligible"] is False
    assert "前置条件未满足" in result["reason"]


def test_revert_execute_completed():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    record = eng.execute(r.id, "sub-1", {})
    assert record.status == "completed"
    assert record.completed_at != ""
    assert record.original_submission_id == "sub-1"


def test_revert_execute_blocked_by_window():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(
        action_id="a", name="n", revert_window_seconds=60,
    ))
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    record = eng.execute(r.id, "sub-1", {"submitted_at": old_time})
    assert record.status == "blocked"
    assert "撤销窗口已过" in record.reason


def test_revert_record_status_transition_invalid():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    record = eng.execute(r.id, "sub-1", {})
    # 已 completed，不能再转换
    with pytest.raises(RevertError) as exc:
        eng.update_record_status(record.id, "in_progress")
    assert exc.value.code == "INVALID_TRANSITION"


def test_revert_record_status_invalid_value():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    record = eng.execute(r.id, "sub-1", {})
    with pytest.raises(RevertError) as exc:
        eng.update_record_status(record.id, "unknown")
    assert exc.value.code == "INVALID_STATUS"


def test_revert_list_records_filter():
    eng = RevertEngine()
    r = eng.create_rule(RevertRule(action_id="a", name="n"))
    eng.execute(r.id, "sub-1", {})
    eng.execute(r.id, "sub-2", {})
    assert len(eng.list_records(rule_id=r.id)) == 2
    assert len(eng.list_records(submission_id="sub-1")) == 1
    assert len(eng.list_records(status="completed")) == 2


def test_revert_get_record_not_found():
    eng = RevertEngine()
    with pytest.raises(RevertError) as exc:
        eng.get_record("nonexistent")
    assert exc.value.code == "NOT_FOUND"
