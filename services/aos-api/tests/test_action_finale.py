"""W2-S · Action 收尾组测试：#67 日志对象类型 + #68 平台集成 + #70 Saga 事务回滚."""
from __future__ import annotations

import pytest

from aos_api.action_finale import (
    ActionBinding,
    ActionBindingEngine,
    ActionBindingError,
    ActionLog,
    ActionLogEngine,
    ActionLogError,
    CompensationStep,
    SagaEngine,
    SagaError,
    SagaTransaction,
    WorkshopButtonGroup,
)


# ── #67 Action 日志对象类型 ──

def test_log_create():
    eng = ActionLogEngine()
    log_obj = eng.create(ActionLog(
        action_id="CreateOrder", actor="user1",
        parameters={"order_id": "o-1", "amount": 100},
    ))
    assert log_obj.id.startswith("log-")
    assert log_obj.version == 1
    assert log_obj.operation_rid.startswith("rid-")
    assert log_obj.status == "submitted"


def test_log_get_not_found():
    eng = ActionLogEngine()
    with pytest.raises(ActionLogError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_log_list_filter():
    eng = ActionLogEngine()
    eng.create(ActionLog(action_id="a1"))
    eng.create(ActionLog(action_id="a2", status="succeeded"))
    assert len(eng.list()) == 2
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list(status="succeeded")) == 1


def test_log_update_status():
    eng = ActionLogEngine()
    log_obj = eng.create(ActionLog(action_id="a"))
    updated = eng.update_status(log_obj.id, "succeeded")
    assert updated.status == "succeeded"


def test_log_invalid_status_on_create():
    eng = ActionLogEngine()
    with pytest.raises(ActionLogError) as exc:
        eng.create(ActionLog(action_id="a", status="unknown"))
    assert exc.value.code == "INVALID_STATUS"


def test_log_invalid_status_on_update():
    eng = ActionLogEngine()
    log_obj = eng.create(ActionLog(action_id="a"))
    with pytest.raises(ActionLogError) as exc:
        eng.update_status(log_obj.id, "unknown")
    assert exc.value.code == "INVALID_STATUS"


def test_log_delete():
    eng = ActionLogEngine()
    log_obj = eng.create(ActionLog(action_id="a"))
    assert eng.delete(log_obj.id) is True
    with pytest.raises(ActionLogError):
        eng.get(log_obj.id)


def test_log_get_log_type():
    eng = ActionLogEngine()
    type_def = eng.get_log_type("CreateOrder")
    assert type_def["object_type"] == "[LOG]CreateOrder"
    assert type_def["title_key"] == "operation_rid"
    assert type_def["primary_key"] == "id"
    prop_names = [p["name"] for p in type_def["properties"]]
    assert "operation_rid" in prop_names
    assert "parameters" in prop_names


def test_log_version_auto_increment():
    eng = ActionLogEngine()
    l1 = eng.create(ActionLog(action_id="a"))
    l2 = eng.create(ActionLog(action_id="a"))
    l3 = eng.create(ActionLog(action_id="a"))
    assert l1.version == 1
    assert l2.version == 2
    assert l3.version == 3


def test_log_explicit_version_preserved():
    eng = ActionLogEngine()
    l = eng.create(ActionLog(action_id="a", version=5))
    assert l.version == 5
    # 后续自增应基于 5
    l_next = eng.create(ActionLog(action_id="a"))
    assert l_next.version == 6


# ── #68 Action 平台集成 ──

def test_binding_create():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a1", integration_type="object_view",
        target_type="object_type", target_id="Order",
        button_label="Create",
    ))
    assert b.id.startswith("bnd-")
    assert b.button_location == "primary"
    assert b.enabled is True


def test_binding_get_not_found():
    eng = ActionBindingEngine()
    with pytest.raises(ActionBindingError) as exc:
        eng.get_binding("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_binding_list_filter():
    eng = ActionBindingEngine()
    eng.create_binding(ActionBinding(
        action_id="a1", integration_type="object_view",
        target_type="object_type", target_id="Order", button_label="x",
    ))
    eng.create_binding(ActionBinding(
        action_id="a2", integration_type="workshop",
        target_type="workshop_module", target_id="m1", button_label="y",
    ))
    assert len(eng.list_bindings()) == 2
    assert len(eng.list_bindings(action_id="a1")) == 1
    assert len(eng.list_bindings(integration_type="workshop")) == 1
    assert len(eng.list_bindings(target_id="Order")) == 1


def test_binding_update():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a", integration_type="object_view",
        target_type="object_type", target_id="T", button_label="L",
    ))
    updated = eng.update_binding(b.id, {"button_label": "renamed", "enabled": False})
    assert updated.button_label == "renamed"
    assert updated.enabled is False


def test_binding_delete():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a", integration_type="object_view",
        target_type="object_type", target_id="T", button_label="L",
    ))
    assert eng.delete_binding(b.id) is True
    with pytest.raises(ActionBindingError):
        eng.get_binding(b.id)


def test_binding_invalid_integration_type():
    eng = ActionBindingEngine()
    with pytest.raises(ActionBindingError) as exc:
        eng.create_binding(ActionBinding(
            action_id="a", integration_type="invalid",
            target_type="object_type", target_id="T", button_label="L",
        ))
    assert exc.value.code == "INVALID_INTEGRATION_TYPE"


def test_binding_invalid_button_location():
    eng = ActionBindingEngine()
    with pytest.raises(ActionBindingError) as exc:
        eng.create_binding(ActionBinding(
            action_id="a", integration_type="object_view",
            target_type="object_type", target_id="T", button_label="L",
            button_location="middle",
        ))
    assert exc.value.code == "INVALID_BUTTON_LOCATION"


def test_binding_evaluate_no_condition():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a", integration_type="object_view",
        target_type="object_type", target_id="T", button_label="L",
    ))
    result = eng.evaluate_binding(b.id, {})
    assert result["visible"] is True


def test_binding_evaluate_with_condition():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a", integration_type="object_view",
        target_type="object_type", target_id="T", button_label="L",
        visibility_condition="status = 'active'",
    ))
    assert eng.evaluate_binding(b.id, {"status": "active"})["visible"] is True
    assert eng.evaluate_binding(b.id, {"status": "inactive"})["visible"] is False


def test_button_group_create():
    eng = ActionBindingEngine()
    g = eng.create_button_group(WorkshopButtonGroup(
        workshop_module="m1", name="Actions",
    ))
    assert g.id.startswith("wbg-")
    assert g.layout == "horizontal"


def test_button_group_get_not_found():
    eng = ActionBindingEngine()
    with pytest.raises(ActionBindingError) as exc:
        eng.get_button_group("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_button_group_list_by_module():
    eng = ActionBindingEngine()
    eng.create_button_group(WorkshopButtonGroup(workshop_module="m1", name="a"))
    eng.create_button_group(WorkshopButtonGroup(workshop_module="m2", name="b"))
    assert len(eng.list_button_groups()) == 2
    assert len(eng.list_button_groups(workshop_module="m1")) == 1


def test_button_group_update_and_delete():
    eng = ActionBindingEngine()
    g = eng.create_button_group(WorkshopButtonGroup(workshop_module="m", name="n"))
    updated = eng.update_button_group(g.id, {"name": "renamed", "layout": "vertical"})
    assert updated.name == "renamed"
    assert updated.layout == "vertical"
    assert eng.delete_button_group(g.id) is True
    with pytest.raises(ActionBindingError):
        eng.get_button_group(g.id)


def test_button_group_invalid_layout():
    eng = ActionBindingEngine()
    with pytest.raises(ActionBindingError) as exc:
        eng.create_button_group(WorkshopButtonGroup(
            workshop_module="m", name="n", layout="diagonal",
        ))
    assert exc.value.code == "INVALID_LAYOUT"


def test_attach_detach_binding():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a", integration_type="workshop",
        target_type="workshop_module", target_id="m", button_label="L",
    ))
    g = eng.create_button_group(WorkshopButtonGroup(workshop_module="m", name="grp"))
    # attach
    g_updated = eng.attach_binding(g.id, b.id)
    assert b.id in g_updated.action_bindings
    # 幂等 attach
    g_updated = eng.attach_binding(g.id, b.id)
    assert g_updated.action_bindings.count(b.id) == 1
    # detach
    g_updated = eng.detach_binding(g.id, b.id)
    assert b.id not in g_updated.action_bindings


def test_attach_binding_not_found():
    eng = ActionBindingEngine()
    g = eng.create_button_group(WorkshopButtonGroup(workshop_module="m", name="grp"))
    with pytest.raises(ActionBindingError) as exc:
        eng.attach_binding(g.id, "nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_delete_binding_removes_from_groups():
    eng = ActionBindingEngine()
    b = eng.create_binding(ActionBinding(
        action_id="a", integration_type="workshop",
        target_type="workshop_module", target_id="m", button_label="L",
    ))
    g = eng.create_button_group(WorkshopButtonGroup(workshop_module="m", name="grp"))
    eng.attach_binding(g.id, b.id)
    assert b.id in eng.get_button_group(g.id).action_bindings
    eng.delete_binding(b.id)
    assert b.id not in eng.get_button_group(g.id).action_bindings


# ── #70 Action Saga 事务回滚 ──

def test_saga_create():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="order_flow",
        forward_steps=[{"step_id": "s1", "action_id": "create_order"}],
        compensation_steps=[
            CompensationStep(step_id="c1", action_id="cancel_order", order=1),
        ],
    ))
    assert s.id.startswith("saga-")
    assert s.status == "pending"
    assert len(s.forward_steps) == 1
    assert len(s.compensation_steps) == 1


def test_saga_get_not_found():
    eng = SagaEngine()
    with pytest.raises(SagaError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_saga_list_filter():
    eng = SagaEngine()
    eng.create(SagaTransaction(name="a"))
    eng.create(SagaTransaction(name="b"))
    assert len(eng.list()) == 2
    assert len(eng.list(status="pending")) == 2
    assert len(eng.list(status="running")) == 0


def test_saga_update():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(name="n"))
    updated = eng.update(s.id, {"name": "renamed"})
    assert updated.name == "renamed"


def test_saga_delete():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(name="n"))
    assert eng.delete(s.id) is True
    with pytest.raises(SagaError):
        eng.get(s.id)


def test_saga_duplicate_order():
    eng = SagaEngine()
    with pytest.raises(SagaError) as exc:
        eng.create(SagaTransaction(
            name="n",
            compensation_steps=[
                CompensationStep(step_id="c1", action_id="a", order=1),
                CompensationStep(step_id="c2", action_id="b", order=1),
            ],
        ))
    assert exc.value.code == "DUPLICATE_ORDER"


def test_saga_start_creates_forward_records():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n",
        forward_steps=[
            {"step_id": "s1", "action_id": "a1"},
            {"step_id": "s2", "action_id": "a2"},
        ],
    ))
    eng.start(s.id)
    saga = eng.get(s.id)
    assert saga.status == "running"
    assert saga.started_at != ""
    records = eng.list_records(s.id)
    assert len(records) == 2
    assert all(r.direction == "forward" for r in records)


def test_saga_start_invalid_transition():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(name="n"))
    eng.start(s.id)
    with pytest.raises(SagaError) as exc:
        eng.start(s.id)
    assert exc.value.code == "INVALID_TRANSITION"


def test_saga_auto_complete_when_all_forward_succeeded():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n",
        forward_steps=[{"step_id": "s1", "action_id": "a1"}],
    ))
    eng.start(s.id)
    records = eng.list_records(s.id)
    eng.update_record_status(s.id, records[0].id, "succeeded")
    saga = eng.get(s.id)
    assert saga.status == "completed"
    assert saga.completed_at != ""


def test_saga_compensate_creates_compensation_records_reverse_order():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n",
        forward_steps=[{"step_id": "s1", "action_id": "a1"}],
        compensation_steps=[
            CompensationStep(step_id="c1", action_id="cancel_a", order=1),
            CompensationStep(step_id="c2", action_id="refund_b", order=2),
        ],
    ))
    eng.start(s.id)
    # forward 失败
    rec = eng.list_records(s.id)[0]
    eng.update_record_status(s.id, rec.id, "failed")
    # 触发补偿
    eng.compensate(s.id)
    saga = eng.get(s.id)
    assert saga.status == "compensating"
    comp_records = eng.list_records(s.id, direction="compensation")
    assert len(comp_records) == 2
    # 倒序：order=2 在前
    assert comp_records[0].step_id == "c2"
    assert comp_records[1].step_id == "c1"


def test_saga_compensate_invalid_transition():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(name="n"))
    with pytest.raises(SagaError) as exc:
        eng.compensate(s.id)
    assert exc.value.code == "INVALID_TRANSITION"


def test_saga_auto_compensated_when_all_compensation_succeeded():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n",
        forward_steps=[{"step_id": "s1", "action_id": "a1"}],
        compensation_steps=[
            CompensationStep(step_id="c1", action_id="cancel", order=1),
        ],
    ))
    eng.start(s.id)
    rec = eng.list_records(s.id)[0]
    eng.update_record_status(s.id, rec.id, "failed")
    eng.compensate(s.id)
    comp_rec = eng.list_records(s.id, direction="compensation")[0]
    eng.update_record_status(s.id, comp_rec.id, "succeeded")
    saga = eng.get(s.id)
    assert saga.status == "compensated"


def test_saga_auto_failed_when_compensation_failed():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n",
        forward_steps=[{"step_id": "s1", "action_id": "a1"}],
        compensation_steps=[
            CompensationStep(step_id="c1", action_id="cancel", order=1),
        ],
    ))
    eng.start(s.id)
    rec = eng.list_records(s.id)[0]
    eng.update_record_status(s.id, rec.id, "failed")
    eng.compensate(s.id)
    comp_rec = eng.list_records(s.id, direction="compensation")[0]
    eng.update_record_status(s.id, comp_rec.id, "failed")
    saga = eng.get(s.id)
    assert saga.status == "failed"


def test_saga_record_invalid_status():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n", forward_steps=[{"step_id": "s1", "action_id": "a1"}],
    ))
    eng.start(s.id)
    rec = eng.list_records(s.id)[0]
    with pytest.raises(SagaError) as exc:
        eng.update_record_status(s.id, rec.id, "unknown")
    assert exc.value.code == "INVALID_STATUS"


def test_saga_record_mismatch():
    eng = SagaEngine()
    s1 = eng.create(SagaTransaction(
        name="n1", forward_steps=[{"step_id": "s1", "action_id": "a1"}],
    ))
    s2 = eng.create(SagaTransaction(
        name="n2", forward_steps=[{"step_id": "s2", "action_id": "a2"}],
    ))
    eng.start(s1.id)
    eng.start(s2.id)
    rec_s1 = eng.list_records(s1.id)[0]
    with pytest.raises(SagaError) as exc:
        eng.update_record_status(s2.id, rec_s1.id, "succeeded")
    assert exc.value.code == "MISMATCH"


def test_saga_get_state():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n",
        forward_steps=[{"step_id": "s1", "action_id": "a1"}],
        compensation_steps=[
            CompensationStep(step_id="c1", action_id="cancel", order=1),
        ],
    ))
    eng.start(s.id)
    state = eng.get_state(s.id)
    assert state["saga_id"] == s.id
    assert state["status"] == "running"
    assert state["total_forward_steps"] == 1
    assert state["total_compensation_steps"] == 1
    assert state["forward_progress"]["pending"] == 1
    assert state["forward_progress"]["succeeded"] == 0


def test_saga_delete_cascades_records():
    eng = SagaEngine()
    s = eng.create(SagaTransaction(
        name="n", forward_steps=[{"step_id": "s1", "action_id": "a1"}],
    ))
    eng.start(s.id)
    assert len(eng.list_records(s.id)) == 1
    eng.delete(s.id)
    # 记录应被级联删除
    assert len(eng.list_records(s.id)) == 0
