"""W2-O · 类型系统与视图配置测试：#52 完整类型系统 + #51 视图配置 + #53 条件格式化."""
from __future__ import annotations

import pytest

from aos_api.type_system import (
    ConditionalFormat,
    FormatEngine,
    FormatError,
    TypeClass,
    TypeDefinition,
    TypeError_,
    TypeSystem,
    ViewProfile,
    ViewProfileEngine,
    ViewProfileError,
    ViewTab,
)


# ── #52 完整类型系统 ──

def test_type_list_builtin():
    eng = TypeSystem()
    types = eng.list_types()
    assert len(types) >= 20
    names = {t.name for t in types}
    assert "String" in names
    assert "Timestamp" in names
    assert "Vector" in names
    assert "Cipher" in names


def test_type_list_by_category():
    eng = TypeSystem()
    scalars = eng.list_types(category="scalar")
    assert all(t.category == "scalar" for t in scalars)
    assert len(scalars) >= 8


def test_type_get():
    eng = TypeSystem()
    td = eng.get_type("Integer")
    assert td.category == "scalar"
    assert td.base_type == "int"


def test_type_get_not_found():
    eng = TypeSystem()
    with pytest.raises(TypeError_) as exc:
        eng.get_type("NonExistent")
    assert exc.value.code == "TYPE_NOT_FOUND"


def test_type_register_custom():
    eng = TypeSystem()
    eng.register_type(TypeDefinition(name="MyType", category="scalar", base_type="str"))
    td = eng.get_type("MyType")
    assert td.name == "MyType"


def test_type_validate_string():
    eng = TypeSystem()
    assert eng.validate("String", "hello") is True
    assert eng.validate("String", 123) is False


def test_type_validate_integer():
    eng = TypeSystem()
    assert eng.validate("Integer", 42) is True
    assert eng.validate("Integer", 42.5) is False
    assert eng.validate("Integer", True) is False  # bool is not int


def test_type_validate_vector():
    eng = TypeSystem()
    assert eng.validate("Vector", [1.0, 2.0, 3.0]) is True
    assert eng.validate("Vector", ["a", "b"]) is False


def test_type_validate_geopoint():
    eng = TypeSystem()
    assert eng.validate("Geopoint", [39.9, 116.4]) is True
    assert eng.validate("Geopoint", [39.9]) is False


def test_type_coerce_string():
    eng = TypeSystem()
    assert eng.coerce("String", 123) == "123"


def test_type_coerce_integer():
    eng = TypeSystem()
    assert eng.coerce("Integer", "42") == 42


def test_type_coerce_no_coercer_returns_original():
    eng = TypeSystem()
    # ByteArray 没有 coercer，应原样返回
    assert eng.coerce("ByteArray", b"data") == b"data"


# ── #51 Object Views 配置文件 ──

def test_vp_create_and_get():
    eng = ViewProfileEngine()
    profile = eng.create(ViewProfile(
        name="Admin View",
        object_type="Employee",
        user_groups=["admin"],
        tabs=[ViewTab(name="Overview", widgets=["grid", "chart"])],
    ))
    fetched = eng.get(profile.id)
    assert fetched.name == "Admin View"
    assert len(fetched.tabs) == 1


def test_vp_get_not_found():
    eng = ViewProfileEngine()
    with pytest.raises(ViewProfileError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_vp_list_filter():
    eng = ViewProfileEngine()
    eng.create(ViewProfile(name="a", object_type="Employee", user_groups=["admin"]))
    eng.create(ViewProfile(name="b", object_type="Department", user_groups=["admin"]))
    assert len(eng.list()) == 2
    assert len(eng.list(object_type="Employee")) == 1
    assert len(eng.list(user_group="admin")) == 2


def test_vp_update():
    eng = ViewProfileEngine()
    profile = eng.create(ViewProfile(name="old", object_type="Employee"))
    updated = eng.update(profile.id, {"name": "new", "is_default": True})
    assert updated.name == "new"
    assert updated.is_default is True


def test_vp_delete():
    eng = ViewProfileEngine()
    profile = eng.create(ViewProfile(name="temp", object_type="Employee"))
    assert eng.delete(profile.id) is True
    with pytest.raises(ViewProfileError):
        eng.get(profile.id)


def test_vp_activate_and_get_active():
    eng = ViewProfileEngine()
    profile = eng.create(ViewProfile(
        name="Admin View",
        object_type="Employee",
        user_groups=["admin"],
    ))
    eng.activate(profile.id, "admin")
    active = eng.get_active("Employee", "admin")
    assert active is not None
    assert active.id == profile.id


def test_vp_get_active_fallback_to_default():
    eng = ViewProfileEngine()
    eng.create(ViewProfile(
        name="Default",
        object_type="Employee",
        is_default=True,
    ))
    # 未激活任何配置，应回退到 default
    active = eng.get_active("Employee", "any_group")
    assert active is not None
    assert active.is_default is True


def test_vp_get_active_none():
    eng = ViewProfileEngine()
    assert eng.get_active("NonExistent", "nobody") is None


# ── #53 值类型/条件格式化/类型类 ──

def test_type_class_list_builtin():
    eng = FormatEngine()
    items = eng.list_type_classes()
    assert len(items) >= 30
    names = {t.name for t in items}
    assert "currency" in names
    assert "percentage" in names
    assert "url" in names


def test_type_class_get():
    eng = FormatEngine()
    tc = eng.get_type_class("currency")
    assert tc.base_type == "Decimal"
    assert tc.render_hint == "symbol:$"


def test_type_class_get_not_found():
    eng = FormatEngine()
    with pytest.raises(FormatError) as exc:
        eng.get_type_class("nonexistent")
    assert exc.value.code == "TYPE_CLASS_NOT_FOUND"


def test_type_class_register_custom():
    eng = FormatEngine()
    eng.register_type_class(TypeClass(name="my_class", base_type="String", render_hint="custom"))
    tc = eng.get_type_class("my_class")
    assert tc.name == "my_class"


def test_render_currency():
    eng = FormatEngine()
    result = eng.render("currency", 99.99)
    assert result["rendered"] == "$99.99"


def test_render_percentage():
    eng = FormatEngine()
    result = eng.render("percentage", 85)
    assert result["rendered"] == "85%"


def test_render_url():
    eng = FormatEngine()
    result = eng.render("url", "https://example.com")
    assert "<a href=" in result["rendered"]


def test_render_file_size():
    eng = FormatEngine()
    assert "KB" in eng.render("file_size", 2048)["rendered"]
    assert "MB" in eng.render("file_size", 2 * 1024 * 1024)["rendered"]
    assert "B" in eng.render("file_size", 512)["rendered"]


def test_conditional_format_create_and_get():
    eng = FormatEngine()
    cf = eng.add_conditional_format(ConditionalFormat(
        object_type="Employee",
        field="salary",
        condition="> 50000",
        style={"color": "red", "bold": True},
    ))
    fetched = eng.get_conditional_format(cf.id)
    assert fetched.field == "salary"
    assert fetched.condition == "> 50000"


def test_conditional_format_list_filter():
    eng = FormatEngine()
    eng.add_conditional_format(ConditionalFormat(object_type="A", field="x", condition="> 1"))
    eng.add_conditional_format(ConditionalFormat(object_type="B", field="y", condition="> 2"))
    assert len(eng.list_conditional_formats()) == 2
    assert len(eng.list_conditional_formats(object_type="A")) == 1
    assert len(eng.list_conditional_formats(field="y")) == 1


def test_conditional_format_delete():
    eng = FormatEngine()
    cf = eng.add_conditional_format(ConditionalFormat(object_type="OT", field="f", condition="> 0"))
    assert eng.delete_conditional_format(cf.id) is True
    with pytest.raises(FormatError):
        eng.get_conditional_format(cf.id)


def test_conditional_format_evaluate_gt():
    eng = FormatEngine()
    cf = eng.add_conditional_format(ConditionalFormat(
        object_type="OT", field="score", condition="> 80",
        style={"color": "green"},
    ))
    result = eng.evaluate(cf.id, 90)
    assert result["matched"] is True
    assert result["style"]["color"] == "green"
    result2 = eng.evaluate(cf.id, 70)
    assert result2["matched"] is False
    assert result2["style"] == {}


def test_conditional_format_evaluate_eq():
    eng = FormatEngine()
    cf = eng.add_conditional_format(ConditionalFormat(
        object_type="OT", field="status", condition="= 'active'",
        style={"color": "blue"},
    ))
    assert eng.evaluate(cf.id, "active")["matched"] is True
    assert eng.evaluate(cf.id, "inactive")["matched"] is False


def test_conditional_format_evaluate_contains():
    eng = FormatEngine()
    cf = eng.add_conditional_format(ConditionalFormat(
        object_type="OT", field="desc", condition="contains 'urgent'",
        style={"color": "red"},
    ))
    assert eng.evaluate(cf.id, "this is urgent matter")["matched"] is True
    assert eng.evaluate(cf.id, "normal text")["matched"] is False
