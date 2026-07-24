"""W2-Q · Action 增强延伸测试：#61 参数筛选 + #62 提交标准 + #63 通知副作用."""
from __future__ import annotations

import pytest

from aos_api.action_further import (
    CriteriaEngine,
    CriteriaError,
    FilterEngine,
    FilterError,
    NotificationEngine,
    NotificationError,
    NotificationSideEffect,
    ParameterFilter,
    SubmissionCriteria,
)


# ── #61 参数筛选 ──

def test_filter_create():
    eng = FilterEngine()
    f = eng.create(ParameterFilter(
        action_id="a1", param_name="target",
        target_object_type="Employee",
    ))
    assert f.id.startswith("pf-")
    assert f.target_object_type == "Employee"


def test_filter_get_not_found():
    eng = FilterEngine()
    with pytest.raises(FilterError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_filter_list_filter_by_action():
    eng = FilterEngine()
    eng.create(ParameterFilter(action_id="a1", param_name="p1"))
    eng.create(ParameterFilter(action_id="a2", param_name="p2"))
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list()) == 2


def test_filter_update():
    eng = FilterEngine()
    f = eng.create(ParameterFilter(action_id="a", param_name="p"))
    updated = eng.update(f.id, {"base_set": "set-1", "security_filter": "level > 5"})
    assert updated.base_set == "set-1"


def test_filter_delete():
    eng = FilterEngine()
    f = eng.create(ParameterFilter(action_id="a", param_name="p"))
    assert eng.delete(f.id) is True
    with pytest.raises(FilterError):
        eng.get(f.id)


def test_filter_apply_with_object_pool():
    eng = FilterEngine()
    eng.register_object_pool("Employee", [
        {"id": "e1", "name": "Alice", "level": 5, "dept": "eng"},
        {"id": "e2", "name": "Bob", "level": 3, "dept": "eng"},
        {"id": "e3", "name": "Carol", "level": 7, "dept": "sales"},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="assignee",
        target_object_type="Employee",
    ))
    result = eng.apply(f.id)
    assert result["count"] == 3


def test_filter_apply_with_base_set():
    eng = FilterEngine()
    eng.register_object_set("set-1", [
        {"id": "e1", "name": "Alice"},
        {"id": "e2", "name": "Bob"},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        base_set="set-1",
    ))
    result = eng.apply(f.id)
    assert result["count"] == 2


def test_filter_apply_with_search_scope():
    eng = FilterEngine()
    eng.register_object_pool("Employee", [
        {"id": "e1", "name": "Alice", "dept": "eng"},
        {"id": "e2", "name": "Bob", "dept": "eng"},
        {"id": "e3", "name": "Carol", "dept": "sales"},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        target_object_type="Employee",
        search_scope={"dept": "eng"},
    ))
    result = eng.apply(f.id)
    assert result["count"] == 2
    names = {o["name"] for o in result["objects"]}
    assert "Alice" in names
    assert "Carol" not in names


def test_filter_apply_with_security_filter():
    eng = FilterEngine()
    eng.register_object_pool("Employee", [
        {"id": "e1", "level": 5},
        {"id": "e2", "level": 3},
        {"id": "e3", "level": 7},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        target_object_type="Employee",
        security_filter="level > 4",
    ))
    result = eng.apply(f.id)
    assert result["count"] == 2


def test_filter_apply_with_ordering():
    eng = FilterEngine()
    eng.register_object_pool("Employee", [
        {"id": "e3", "level": 7},
        {"id": "e1", "level": 5},
        {"id": "e2", "level": 3},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        target_object_type="Employee",
        ordering=[{"field": "level", "direction": "asc"}],
    ))
    result = eng.apply(f.id)
    assert [o["level"] for o in result["objects"]] == [3, 5, 7]


def test_filter_apply_with_ordering_desc():
    eng = FilterEngine()
    eng.register_object_pool("Employee", [
        {"id": "e3", "level": 7},
        {"id": "e1", "level": 5},
        {"id": "e2", "level": 3},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        target_object_type="Employee",
        ordering=[{"field": "level", "direction": "desc"}],
    ))
    result = eng.apply(f.id)
    assert [o["level"] for o in result["objects"]] == [7, 5, 3]


def test_filter_apply_with_template_in_scope():
    """search_scope 支持 {{var}} 上下文变量替换。"""
    eng = FilterEngine()
    eng.register_object_pool("Employee", [
        {"id": "e1", "dept": "eng"},
        {"id": "e2", "dept": "sales"},
    ])
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        target_object_type="Employee",
        search_scope={"dept": "{{target_dept}}"},
    ))
    result = eng.apply(f.id, {"target_dept": "eng"})
    assert result["count"] == 1
    assert result["objects"][0]["id"] == "e1"


def test_filter_apply_empty_pool():
    eng = FilterEngine()
    f = eng.create(ParameterFilter(
        action_id="a", param_name="target",
        target_object_type="Nonexistent",
    ))
    result = eng.apply(f.id)
    assert result["count"] == 0


# ── #62 提交标准 ──

def test_criteria_create():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a1", name="min_amount",
        condition_tree={"field": "amount", "op": ">", "value": 100},
    ))
    assert c.id.startswith("sc-")
    assert c.severity == "error"  # default


def test_criteria_create_invalid_severity():
    eng = CriteriaEngine()
    with pytest.raises(CriteriaError) as exc:
        eng.create(SubmissionCriteria(
            action_id="a", name="x",
            condition_tree={"field": "x", "op": "=", "value": 1},
            severity="critical",
        ))
    assert exc.value.code == "INVALID_SEVERITY"


def test_criteria_create_empty_tree():
    eng = CriteriaEngine()
    with pytest.raises(CriteriaError) as exc:
        eng.create(SubmissionCriteria(
            action_id="a", name="x", condition_tree={},
        ))
    assert exc.value.code == "EMPTY_TREE"


def test_criteria_get_not_found():
    eng = CriteriaEngine()
    with pytest.raises(CriteriaError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_criteria_list_filter():
    eng = CriteriaEngine()
    eng.create(SubmissionCriteria(action_id="a1", name="c1", condition_tree={"field": "x", "op": "=", "value": 1}))
    eng.create(SubmissionCriteria(action_id="a2", name="c2", condition_tree={"field": "x", "op": "=", "value": 2}))
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list()) == 2


def test_criteria_update():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="c", condition_tree={"field": "x", "op": "=", "value": 1},
    ))
    updated = eng.update(c.id, {"name": "renamed", "severity": "warning"})
    assert updated.name == "renamed"
    assert updated.severity == "warning"


def test_criteria_delete():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="c", condition_tree={"field": "x", "op": "=", "value": 1},
    ))
    assert eng.delete(c.id) is True
    with pytest.raises(CriteriaError):
        eng.get(c.id)


def test_criteria_evaluate_leaf_pass():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="min_amount",
        condition_tree={"field": "amount", "op": ">", "value": 100},
    ))
    result = eng.evaluate(c.id, {"amount": 150})
    assert result["passed"] is True
    assert result["failure_message"] == ""


def test_criteria_evaluate_leaf_fail():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="min_amount",
        condition_tree={"field": "amount", "op": ">", "value": 100},
        failure_message="金额必须大于 100",
    ))
    result = eng.evaluate(c.id, {"amount": 50})
    assert result["passed"] is False
    assert result["failure_message"] == "金额必须大于 100"
    assert result["severity"] == "error"


def test_criteria_evaluate_and():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="both",
        condition_tree={
            "op": "AND",
            "children": [
                {"field": "amount", "op": ">", "value": 100},
                {"field": "status", "op": "=", "value": "active"},
            ],
        },
    ))
    assert eng.evaluate(c.id, {"amount": 150, "status": "active"})["passed"] is True
    assert eng.evaluate(c.id, {"amount": 150, "status": "inactive"})["passed"] is False
    assert eng.evaluate(c.id, {"amount": 50, "status": "active"})["passed"] is False


def test_criteria_evaluate_or():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="either",
        condition_tree={
            "op": "OR",
            "children": [
                {"field": "role", "op": "=", "value": "admin"},
                {"field": "role", "op": "=", "value": "owner"},
            ],
        },
    ))
    assert eng.evaluate(c.id, {"role": "admin"})["passed"] is True
    assert eng.evaluate(c.id, {"role": "owner"})["passed"] is True
    assert eng.evaluate(c.id, {"role": "viewer"})["passed"] is False


def test_criteria_evaluate_not():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="not_draft",
        condition_tree={
            "op": "NOT",
            "children": [{"field": "status", "op": "=", "value": "draft"}],
        },
    ))
    assert eng.evaluate(c.id, {"status": "active"})["passed"] is True
    assert eng.evaluate(c.id, {"status": "draft"})["passed"] is False


def test_criteria_evaluate_nested():
    """嵌套：(A AND B) OR (NOT C)。"""
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="nested",
        condition_tree={
            "op": "OR",
            "children": [
                {
                    "op": "AND",
                    "children": [
                        {"field": "level", "op": ">=", "value": 5},
                        {"field": "dept", "op": "=", "value": "eng"},
                    ],
                },
                {
                    "op": "NOT",
                    "children": [{"field": "fired", "op": "=", "value": True}],
                },
            ],
        },
    ))
    # A AND B 匹配
    assert eng.evaluate(c.id, {"level": 7, "dept": "eng", "fired": True})["passed"] is True
    # NOT C 匹配（fired=False）
    assert eng.evaluate(c.id, {"level": 1, "dept": "sales", "fired": False})["passed"] is True
    # 都不匹配
    assert eng.evaluate(c.id, {"level": 1, "dept": "sales", "fired": True})["passed"] is False


def test_criteria_evaluate_contains():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="has_keyword",
        condition_tree={"field": "description", "op": "contains", "value": "urgent"},
    ))
    assert eng.evaluate(c.id, {"description": "this is urgent"})["passed"] is True
    assert eng.evaluate(c.id, {"description": "normal task"})["passed"] is False


def test_criteria_evaluate_in():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="in_list",
        condition_tree={"field": "status", "op": "in", "value": ["draft", "pending"]},
    ))
    assert eng.evaluate(c.id, {"status": "draft"})["passed"] is True
    assert eng.evaluate(c.id, {"status": "published"})["passed"] is False


def test_criteria_evaluate_exists():
    eng = CriteriaEngine()
    c = eng.create(SubmissionCriteria(
        action_id="a", name="has_id",
        condition_tree={"field": "id", "op": "exists", "value": True},
    ))
    assert eng.evaluate(c.id, {"id": "x"})["passed"] is True
    assert eng.evaluate(c.id, {})["passed"] is False


# ── #63 通知副作用 ──

def test_notification_create_static():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(
        action_id="a1", name="notify_admin",
        recipient_source="static",
        recipients=["admin@example.com", "boss@example.com"],
        subject_template="Action {{action_name}} triggered",
        body_template="User {{user}} performed {{action_name}}",
    ))
    assert e.id.startswith("nse-")
    assert e.recipient_source == "static"
    assert e.channel == "email"


def test_notification_create_invalid_source():
    eng = NotificationEngine()
    with pytest.raises(NotificationError) as exc:
        eng.create(NotificationSideEffect(
            action_id="a", name="x", recipient_source="unknown",
        ))
    assert exc.value.code == "INVALID_SOURCE"


def test_notification_create_invalid_channel():
    eng = NotificationEngine()
    with pytest.raises(NotificationError) as exc:
        eng.create(NotificationSideEffect(
            action_id="a", name="x", channel="unknown",
        ))
    assert exc.value.code == "INVALID_CHANNEL"


def test_notification_get_not_found():
    eng = NotificationEngine()
    with pytest.raises(NotificationError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_notification_list_filter():
    eng = NotificationEngine()
    eng.create(NotificationSideEffect(action_id="a1", name="n1"))
    eng.create(NotificationSideEffect(action_id="a2", name="n2"))
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list()) == 2


def test_notification_update():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(action_id="a", name="n"))
    updated = eng.update(e.id, {"subject_template": "Updated {{x}}", "channel": "sms"})
    assert updated.subject_template == "Updated {{x}}"
    assert updated.channel == "sms"


def test_notification_delete():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(action_id="a", name="n"))
    assert eng.delete(e.id) is True
    with pytest.raises(NotificationError):
        eng.get(e.id)


def test_notification_render_static_recipients():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="static",
        recipients=["alice@example.com"],
        subject_template="Hello {{user}}",
        body_template="Hi {{user}}, action {{action}} done",
    ))
    rendered = eng.render(e.id, {"user": "Bob", "action": "create"})
    assert rendered["recipients"] == ["alice@example.com"]
    assert rendered["subject"] == "Hello Bob"
    assert rendered["body"] == "Hi Bob, action create done"


def test_notification_render_parameter_recipients():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="parameter",
        recipient_ref="approvers",
    ))
    rendered = eng.render(e.id, {"approvers": ["alice@example.com", "bob@example.com"]})
    assert rendered["recipients"] == ["alice@example.com", "bob@example.com"]


def test_notification_render_object_property_recipients():
    eng = NotificationEngine()
    eng.register_object("Employee", {"id": "emp-1", "email": "alice@example.com", "name": "Alice"})
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="object_property",
        recipient_ref="Employee.emp-1.email",
    ))
    rendered = eng.render(e.id, {})
    assert rendered["recipients"] == ["alice@example.com"]


def test_notification_render_function_recipients():
    eng = NotificationEngine()
    def get_managers(ctx):
        return [f"mgr-{ctx.get('dept', 'unknown')}@example.com"]
    eng.register_function("get_managers", get_managers)
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="function",
        recipient_ref="get_managers",
    ))
    rendered = eng.render(e.id, {"dept": "eng"})
    assert rendered["recipients"] == ["mgr-eng@example.com"]


def test_notification_render_function_returns_list():
    eng = NotificationEngine()
    def get_all(ctx):
        return ["a@x.com", "b@x.com", "c@x.com"]
    eng.register_function("get_all", get_all)
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="function",
        recipient_ref="get_all",
    ))
    rendered = eng.render(e.id, {})
    assert len(rendered["recipients"]) == 3


def test_notification_render_missing_template():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="static", recipients=["x@y.com"],
    ))
    rendered = eng.render(e.id, {})
    assert rendered["subject"] == ""
    assert rendered["body"] == ""


def test_notification_dispatch():
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        recipient_source="static", recipients=["alice@example.com"],
        subject_template="Hello",
        body_template="Body",
    ))
    record = eng.dispatch(e.id, {})
    assert record["status"] == "queued"
    assert record["recipients"] == ["alice@example.com"]
    assert record["dispatch_id"].startswith("disp-")
    # 派发记录可查
    dispatches = eng.list_dispatches(effect_id=e.id)
    assert len(dispatches) == 1


def test_notification_dispatches_filter_by_effect():
    eng = NotificationEngine()
    e1 = eng.create(NotificationSideEffect(action_id="a", name="n1", recipients=["a@x.com"]))
    e2 = eng.create(NotificationSideEffect(action_id="a", name="n2", recipients=["b@x.com"]))
    eng.dispatch(e1.id, {})
    eng.dispatch(e1.id, {})
    eng.dispatch(e2.id, {})
    assert len(eng.list_dispatches(effect_id=e1.id)) == 2
    assert len(eng.list_dispatches()) == 3


def test_notification_render_template_unknown_var_preserved():
    """模板变量未在 context 中提供时保留原 {{var}}。"""
    eng = NotificationEngine()
    e = eng.create(NotificationSideEffect(
        action_id="a", name="n",
        subject_template="Hello {{unknown_var}}",
    ))
    rendered = eng.render(e.id, {})
    assert rendered["subject"] == "Hello {{unknown_var}}"
