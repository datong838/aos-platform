"""W2-P · Action 参数增强测试：#58 约束 + #59 默认值 + #60 覆盖."""
from __future__ import annotations

import os

import pytest

from aos_api.action_params import (
    ConstraintEngine,
    ConstraintError,
    DefaultEngine,
    DefaultError,
    OverrideEngine,
    OverrideError,
    ParameterConstraint,
    ParameterDefault,
    ParameterOverride,
)


# ── #58 参数约束 ──

def test_constraint_create_user_input():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="act-1", param_name="count",
        constraint_type="user_input",
        config={"min": 1, "max": 100, "required": True},
    ))
    assert c.id.startswith("pc-")
    assert c.action_id == "act-1"
    assert c.constraint_type == "user_input"


def test_constraint_create_invalid_type():
    eng = ConstraintEngine()
    with pytest.raises(ConstraintError) as exc:
        eng.create(ParameterConstraint(
            action_id="act-1", param_name="x",
            constraint_type="unknown_type",
        ))
    assert exc.value.code == "INVALID_TYPE"


def test_constraint_get_not_found():
    eng = ConstraintEngine()
    with pytest.raises(ConstraintError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_constraint_list_filter_by_action():
    eng = ConstraintEngine()
    eng.create(ParameterConstraint(action_id="a1", param_name="p1", constraint_type="user_input"))
    eng.create(ParameterConstraint(action_id="a2", param_name="p2", constraint_type="user_input"))
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list()) == 2


def test_constraint_update():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a1", param_name="p1", constraint_type="user_input", config={"min": 0},
    ))
    updated = eng.update(c.id, {"config": {"min": 5, "max": 10}})
    assert updated.config == {"min": 5, "max": 10}


def test_constraint_delete():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(action_id="a1", param_name="p1", constraint_type="user_input"))
    assert eng.delete(c.id) is True
    with pytest.raises(ConstraintError):
        eng.get(c.id)


def test_constraint_validate_user_input_min_max():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="count", constraint_type="user_input",
        config={"min": 1, "max": 100},
    ))
    assert eng.validate_value(c.id, 50)["valid"] is True
    assert eng.validate_value(c.id, 0)["valid"] is False
    assert eng.validate_value(c.id, 200)["valid"] is False


def test_constraint_validate_user_input_pattern():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="email", constraint_type="user_input",
        config={"pattern": r"^[^@]+@[^@]+$"},
    ))
    assert eng.validate_value(c.id, "alice@example.com")["valid"] is True
    assert eng.validate_value(c.id, "not-an-email")["valid"] is False


def test_constraint_validate_user_input_required():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="name", constraint_type="user_input",
        config={"required": True},
    ))
    assert eng.validate_value(c.id, "")["valid"] is False
    assert eng.validate_value(c.id, None)["valid"] is False
    assert eng.validate_value(c.id, "Alice")["valid"] is True


def test_constraint_validate_multiple_choice_single():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="color", constraint_type="multiple_choice",
        config={"options": ["red", "green", "blue"]},
    ))
    assert eng.validate_value(c.id, "red")["valid"] is True
    assert eng.validate_value(c.id, "yellow")["valid"] is False


def test_constraint_validate_multiple_choice_list():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="colors", constraint_type="multiple_choice",
        config={"options": ["red", "green", "blue"]},
    ))
    assert eng.validate_value(c.id, ["red", "green"])["valid"] is True
    assert eng.validate_value(c.id, ["red", "yellow"])["valid"] is False


def test_constraint_get_options_multiple_choice():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="color", constraint_type="multiple_choice",
        config={"options": ["red", "green"]},
    ))
    assert eng.get_options(c.id) == ["red", "green"]


def test_constraint_get_options_user_input_empty():
    eng = ConstraintEngine()
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="name", constraint_type="user_input",
    ))
    assert eng.get_options(c.id) == []


def test_constraint_object_set_validate():
    eng = ConstraintEngine()
    eng.register_object_set("set-1", [
        {"id": "obj-1", "name": "Alice"},
        {"id": "obj-2", "name": "Bob"},
    ])
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="target", constraint_type="object_set",
        config={"object_set_id": "set-1", "key_field": "id"},
    ))
    assert eng.validate_value(c.id, "obj-1")["valid"] is True
    assert eng.validate_value(c.id, "obj-3")["valid"] is False
    # list value
    assert eng.validate_value(c.id, ["obj-1", "obj-2"])["valid"] is True
    assert eng.validate_value(c.id, ["obj-1", "obj-3"])["valid"] is False


def test_constraint_object_set_get_options():
    eng = ConstraintEngine()
    eng.register_object_set("set-1", [
        {"id": "obj-1"},
        {"id": "obj-2"},
    ])
    c = eng.create(ParameterConstraint(
        action_id="a", param_name="target", constraint_type="object_set",
        config={"object_set_id": "set-1"},
    ))
    assert eng.get_options(c.id) == ["obj-1", "obj-2"]


# ── #59 参数默认值 ──

def test_default_create_static():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a1", param_name="count",
        source="static", value=10,
    ))
    assert d.id.startswith("pd-")
    assert d.source == "static"
    assert d.value == 10


def test_default_create_invalid_source():
    eng = DefaultEngine()
    with pytest.raises(DefaultError) as exc:
        eng.create(ParameterDefault(
            action_id="a", param_name="p", source="unknown_source",
        ))
    assert exc.value.code == "INVALID_SOURCE"


def test_default_get_not_found():
    eng = DefaultEngine()
    with pytest.raises(DefaultError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_default_list_filter():
    eng = DefaultEngine()
    eng.create(ParameterDefault(action_id="a1", param_name="p1", source="static", value=1))
    eng.create(ParameterDefault(action_id="a2", param_name="p2", source="static", value=2))
    assert len(eng.list(action_id="a1")) == 1
    assert len(eng.list()) == 2


def test_default_update():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(action_id="a", param_name="p", source="static", value=1))
    updated = eng.update(d.id, {"value": 99, "fallback": 0})
    assert updated.value == 99
    assert updated.fallback == 0


def test_default_delete():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(action_id="a", param_name="p", source="static"))
    assert eng.delete(d.id) is True
    with pytest.raises(DefaultError):
        eng.get(d.id)


def test_default_resolve_static():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a", param_name="count", source="static", value=42,
    ))
    result = eng.resolve(d.id)
    assert result["value"] == 42
    assert result["resolved"] is True


def test_default_resolve_type_class():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a", param_name="name", source="type_class", value="String",
    ))
    result = eng.resolve(d.id)
    assert result["value"] == ""
    assert result["resolved"] is True


def test_default_resolve_type_class_with_fallback():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a", param_name="x", source="type_class", value="UnknownType",
        fallback="default",
    ))
    result = eng.resolve(d.id)
    assert result["value"] == "default"


def test_default_resolve_object_property():
    eng = DefaultEngine()
    eng.register_object("Employee", {"id": "emp-1", "name": "Alice", "age": 30})
    d = eng.create(ParameterDefault(
        action_id="a", param_name="owner",
        source="object_property", value="Employee.emp-1.name",
    ))
    result = eng.resolve(d.id)
    assert result["value"] == "Alice"
    assert result["resolved"] is True


def test_default_resolve_object_property_missing():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a", param_name="owner",
        source="object_property", value="Employee.emp-999.name",
        fallback="unknown",
    ))
    result = eng.resolve(d.id)
    assert result["value"] == "unknown"
    assert result["resolved"] is False


def test_default_resolve_environment(monkeypatch):
    monkeypatch.setenv("AOS_TEST_DEFAULT", "env_value")
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a", param_name="region",
        source="environment", value="AOS_TEST_DEFAULT",
    ))
    result = eng.resolve(d.id)
    assert result["value"] == "env_value"
    assert result["resolved"] is True


def test_default_resolve_environment_missing():
    eng = DefaultEngine()
    d = eng.create(ParameterDefault(
        action_id="a", param_name="region",
        source="environment", value="AOS_NONEXISTENT_VAR_XYZ",
        fallback="us-east-1",
    ))
    result = eng.resolve(d.id)
    assert result["value"] == "us-east-1"
    assert result["resolved"] is False


# ── #60 参数覆盖 ──

def test_override_create():
    eng = OverrideEngine()
    o = eng.create(ParameterOverride(
        action_id="a1", param_name="target",
        condition="status = active",
        overrides={"visible": True, "required": True},
    ))
    assert o.id.startswith("po-")
    assert o.action_id == "a1"


def test_override_get_not_found():
    eng = OverrideEngine()
    with pytest.raises(OverrideError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_override_list_filter():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a1", param_name="p1", condition="x = 1", overrides={"visible": False},
    ))
    eng.create(ParameterOverride(
        action_id="a1", param_name="p2", condition="x = 2", overrides={"required": True},
    ))
    eng.create(ParameterOverride(
        action_id="a2", param_name="p1", condition="x = 3", overrides={},
    ))
    assert len(eng.list(action_id="a1")) == 2
    assert len(eng.list(action_id="a1", param_name="p1")) == 1
    assert len(eng.list()) == 3


def test_override_update():
    eng = OverrideEngine()
    o = eng.create(ParameterOverride(
        action_id="a", param_name="p", condition="x = 1", overrides={"visible": True},
    ))
    updated = eng.update(o.id, {"condition": "y = 2", "overrides": {"disabled": True}})
    assert updated.condition == "y = 2"
    assert updated.overrides == {"disabled": True}


def test_override_delete():
    eng = OverrideEngine()
    o = eng.create(ParameterOverride(
        action_id="a", param_name="p", condition="x = 1",
    ))
    assert eng.delete(o.id) is True
    with pytest.raises(OverrideError):
        eng.get(o.id)


def test_override_evaluate_empty_condition():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p", condition="",
        overrides={"visible": False, "required": True},
    ))
    result = eng.evaluate("a", "p", {})
    assert result["visible"] is False
    assert result["required"] is True
    assert result["disabled"] is False  # default


def test_override_evaluate_equal_condition():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="status = active",
        overrides={"required": True},
    ))
    # 匹配
    result = eng.evaluate("a", "p", {"status": "active"})
    assert result["required"] is True
    assert len(result["applied_overrides"]) == 1
    # 不匹配
    result = eng.evaluate("a", "p", {"status": "inactive"})
    assert result["required"] is False
    assert len(result["applied_overrides"]) == 0


def test_override_evaluate_not_equal():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="status != draft",
        overrides={"visible": True},
    ))
    assert eng.evaluate("a", "p", {"status": "active"})["visible"] is True
    # 不匹配（draft == draft）
    result = eng.evaluate("a", "p", {"status": "draft"})
    assert result["visible"] is True  # 默认值仍为 True


def test_override_evaluate_numeric_comparison():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="count > 10",
        overrides={"disabled": True},
    ))
    assert eng.evaluate("a", "p", {"count": 50})["disabled"] is True
    assert eng.evaluate("a", "p", {"count": 5})["disabled"] is False


def test_override_evaluate_multiple_merge():
    """多个匹配覆盖块合并：后续覆盖前者。"""
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="status = active",
        overrides={"visible": True, "required": True},
    ))
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="level = admin",
        overrides={"disabled": False, "required": False},
    ))
    result = eng.evaluate("a", "p", {"status": "active", "level": "admin"})
    # 两个块都匹配：required 由第二个覆盖为 False
    assert result["visible"] is True
    assert result["required"] is False
    assert result["disabled"] is False
    assert len(result["applied_overrides"]) == 2


def test_override_evaluate_no_match():
    """无覆盖块时返回默认三态。"""
    eng = OverrideEngine()
    result = eng.evaluate("a", "nonexistent_param", {})
    assert result["visible"] is True
    assert result["disabled"] is False
    assert result["required"] is False
    assert result["applied_overrides"] == []


def test_override_evaluate_ge_le():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="age >= 18",
        overrides={"required": True},
    ))
    assert eng.evaluate("a", "p", {"age": 18})["required"] is True
    assert eng.evaluate("a", "p", {"age": 17})["required"] is False


def test_override_evaluate_invalid_numeric_returns_false():
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="age > 18",
        overrides={"required": True},
    ))
    # 非数字比较 → False
    result = eng.evaluate("a", "p", {"age": "not-a-number"})
    assert result["required"] is False


def test_override_evaluate_unmatched_condition_returns_false():
    """无操作符的条件返回 False（不触发）。"""
    eng = OverrideEngine()
    eng.create(ParameterOverride(
        action_id="a", param_name="p",
        condition="some random text without operator",
        overrides={"visible": False},
    ))
    result = eng.evaluate("a", "p", {})
    # 默认 visible=True（覆盖未触发）
    assert result["visible"] is True
    assert len(result["applied_overrides"]) == 0
