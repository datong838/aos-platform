"""W2-#21 · @transform 装饰器与 OP_CATALOG 测试。"""
from __future__ import annotations

import pytest

from aos_api.transform_ops import (
    TRANSFORM_REGISTRY,
    TransformError,
    TransformOpMeta,
    _OP_META,
    apply_transform,
    list_op_catalog,
    register_transform,
)


@pytest.fixture(autouse=True)
def _restore_registry():
    """快照并恢复全局注册表，防止装饰器测试污染其他测试。"""
    saved_registry = dict(TRANSFORM_REGISTRY)
    saved_meta = {k: v.model_copy() for k, v in _OP_META.items()}
    yield
    TRANSFORM_REGISTRY.clear()
    TRANSFORM_REGISTRY.update(saved_registry)
    _OP_META.clear()
    _OP_META.update(saved_meta)


def test_builtin_catalog_has_nine_ops():
    catalog = {m.name: m for m in list_op_catalog()}
    expected = {"filter", "join", "aggregate", "explode", "cast", "union", "sort", "distinct", "expression"}
    assert expected.issubset(catalog.keys())
    for name in expected:
        assert catalog[name].description != "", f"{name} 缺少描述"


def test_register_transform_decorator_adds_to_registry():
    @register_transform("deco_double", description="字段翻倍", config_schema={"field": "str"})
    def op_double(rows, config):
        field = config.get("field", "v")
        return [{**r, field: r.get(field, 0) * 2} for r in rows]

    assert "deco_double" in TRANSFORM_REGISTRY
    catalog = {m.name: m for m in list_op_catalog()}
    assert catalog["deco_double"].description == "字段翻倍"
    assert catalog["deco_double"].config_schema == {"field": "str"}


def test_registered_transform_executable():
    @register_transform("deco_add_prefix")
    def op_prefix(rows, config):
        prefix = config.get("prefix", "P-")
        return [{**r, "label": prefix + str(r.get("name", ""))} for r in rows]

    result = apply_transform("deco_add_prefix", [{"name": "a"}, {"name": "b"}], {"prefix": "X-"})
    assert result == [{"name": "a", "label": "X-a"}, {"name": "b", "label": "X-b"}]


def test_decorator_returns_original_callable():
    @register_transform("deco_identity_v2")
    def op_identity(rows, config):
        return list(rows)

    assert callable(op_identity)
    assert op_identity([{"x": 1}], {}) == [{"x": 1}]


def test_register_overrides_existing_name():
    @register_transform("deco_override")
    def op_v1(rows, config):
        return ["v1"]

    @register_transform("deco_override", description="v2 版本")
    def op_v2(rows, config):
        return ["v2"]

    assert apply_transform("deco_override", [], {}) == ["v2"]
    catalog = {m.name: m for m in list_op_catalog()}
    assert catalog["deco_override"].description == "v2 版本"


def test_builtin_filter_still_works_after_decoration():
    result = apply_transform("filter", [{"a": 1}, {"a": 2}], {"expression": "a > 1"})
    assert result == [{"a": 2}]


def test_unknown_op_still_raises():
    with pytest.raises(TransformError) as exc:
        apply_transform("nonexistent_xyz", [], {})
    assert exc.value.code == "UNKNOWN_OP"


def test_catalog_entries_are_transformopmeta():
    for m in list_op_catalog():
        assert isinstance(m, TransformOpMeta)


def test_catalog_is_defensive_copy():
    catalog_first = list_op_catalog()
    catalog_first[0].description = "MUTATED"
    catalog_second = list_op_catalog()
    assert catalog_second[0].description != "MUTATED"


def test_config_schema_propagation():
    schema = {"field": "str", "required": True}

    @register_transform("deco_with_schema", config_schema=schema)
    def op(rows, config):
        return rows

    catalog = {m.name: m for m in list_op_catalog()}
    assert catalog["deco_with_schema"].config_schema == schema
