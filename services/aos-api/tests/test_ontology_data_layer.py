"""W2-L · Object 数据层增强测试：#33 Shared Property + #29 Type Coherence + #30 L1 Join + Computed Property."""
from __future__ import annotations

import pytest

from aos_api.ontology_data_layer import (
    ComputedProperty,
    JoinSpec,
    L1JoinConfig,
    L1JoinEngine,
    L1JoinError,
    SharedProperty,
    SharedPropertyEngine,
    SharedPropertyError,
    TypeCoherenceEngine,
)


# ── #33 Shared Property ──

def test_sp_create_and_get():
    eng = SharedPropertyEngine()
    prop = eng.create(SharedProperty(name="email", data_type="string", backing_column="email"))
    fetched = eng.get(prop.id)
    assert fetched.name == "email"
    assert fetched.data_type == "string"


def test_sp_get_not_found():
    eng = SharedPropertyEngine()
    with pytest.raises(SharedPropertyError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_sp_list():
    eng = SharedPropertyEngine()
    eng.create(SharedProperty(name="a"))
    eng.create(SharedProperty(name="b"))
    assert len(eng.list()) == 2


def test_sp_update():
    eng = SharedPropertyEngine()
    prop = eng.create(SharedProperty(name="email", data_type="string"))
    updated = eng.update(prop.id, {"description": "user email", "nullable": False})
    assert updated.description == "user email"
    assert updated.nullable is False


def test_sp_update_preserves_id_and_created_at():
    eng = SharedPropertyEngine()
    prop = eng.create(SharedProperty(name="x"))
    original_id = prop.id
    original_created = prop.created_at
    eng.update(prop.id, {"name": "y"})
    assert prop.id == original_id
    assert prop.created_at == original_created


def test_sp_attach_and_detach():
    eng = SharedPropertyEngine()
    prop = eng.create(SharedProperty(name="email"))
    attached = eng.attach(prop.id, "Employee")
    assert "Employee" in attached.referenced_by
    # 幂等
    eng.attach(prop.id, "Employee")
    assert attached.referenced_by.count("Employee") == 1
    detached = eng.detach(prop.id, "Employee")
    assert "Employee" not in detached.referenced_by


def test_sp_delete_when_referenced_blocked():
    eng = SharedPropertyEngine()
    prop = eng.create(SharedProperty(name="email"))
    eng.attach(prop.id, "Employee")
    with pytest.raises(SharedPropertyError) as exc:
        eng.delete(prop.id)
    assert exc.value.code == "STILL_REFERENCED"


def test_sp_delete_when_not_referenced():
    eng = SharedPropertyEngine()
    prop = eng.create(SharedProperty(name="email"))
    assert eng.delete(prop.id) is True
    with pytest.raises(SharedPropertyError):
        eng.get(prop.id)


# ── #29 Type Coherence ──

def test_tc_check_no_conflict():
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "Employee",
        properties=[{"name": "email", "data_type": "string", "backing_column": "email", "nullable": True}],
        dataset_columns=[{"name": "email", "data_type": "string", "nullable": True}],
    )
    conflicts = eng.check("Employee")
    assert conflicts == []


def test_tc_tc01_type_mismatch():
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "OT",
        properties=[{"name": "age", "data_type": "string", "backing_column": "age", "nullable": True}],
        dataset_columns=[{"name": "age", "data_type": "int", "nullable": True}],
    )
    conflicts = eng.check("OT")
    assert any(c.code == "TC-01" for c in conflicts)


def test_tc_tc01_type_compatible_group():
    """同兼容组（string/text）不应触发 TC-01。"""
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "OT",
        properties=[{"name": "name", "data_type": "string", "backing_column": "name", "nullable": True}],
        dataset_columns=[{"name": "name", "data_type": "text", "nullable": True}],
    )
    conflicts = eng.check("OT")
    assert not any(c.code == "TC-01" for c in conflicts)


def test_tc_tc02_missing_column():
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "OT",
        properties=[{"name": "phone", "data_type": "string", "backing_column": "phone_col", "nullable": True}],
        dataset_columns=[{"name": "email", "data_type": "string", "nullable": True}],
    )
    conflicts = eng.check("OT")
    assert any(c.code == "TC-02" for c in conflicts)


def test_tc_tc03_extra_column():
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "OT",
        properties=[{"name": "email", "data_type": "string", "backing_column": "email", "nullable": True}],
        dataset_columns=[
            {"name": "email", "data_type": "string", "nullable": True},
            {"name": "extra_col", "data_type": "string", "nullable": True},
        ],
    )
    conflicts = eng.check("OT")
    tc03 = [c for c in conflicts if c.code == "TC-03"]
    assert len(tc03) == 1
    assert tc03[0].detail["column"] == "extra_col"


def test_tc_tc04_nullable_conflict():
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "OT",
        properties=[{"name": "id", "data_type": "int", "backing_column": "id", "nullable": False}],
        dataset_columns=[{"name": "id", "data_type": "int", "nullable": True}],
    )
    conflicts = eng.check("OT")
    assert any(c.code == "TC-04" for c in conflicts)


def test_tc_check_all_multiple_ots():
    eng = TypeCoherenceEngine()
    eng.register_schema(
        "OT1",
        properties=[{"name": "a", "data_type": "string", "backing_column": "a", "nullable": True}],
        dataset_columns=[{"name": "a", "data_type": "int", "nullable": True}],
    )
    eng.register_schema(
        "OT2",
        properties=[{"name": "b", "data_type": "string", "backing_column": "missing", "nullable": True}],
        dataset_columns=[{"name": "b", "data_type": "string", "nullable": True}],
    )
    all_conflicts = eng.check_all()
    assert len(all_conflicts) >= 2
    ots = {c.object_type for c in all_conflicts}
    assert "OT1" in ots
    assert "OT2" in ots


def test_tc_check_unregistered_returns_empty():
    eng = TypeCoherenceEngine()
    assert eng.check("NonExistent") == []


# ── #30 L1 Join + Computed Property ──

def test_l1_join_create_and_get():
    eng = L1JoinEngine()
    config = eng.create_join(L1JoinConfig(
        object_type="Employee",
        primary_dataset="ds_emp",
        primary_key="emp_id",
        joins=[JoinSpec(dataset="ds_dept", left_key="dept_id", right_key="dept_id")],
    ))
    fetched = eng.get_join(config.id)
    assert fetched.object_type == "Employee"
    assert len(fetched.joins) == 1


def test_l1_join_get_not_found():
    eng = L1JoinEngine()
    with pytest.raises(L1JoinError) as exc:
        eng.get_join("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_l1_join_list_filter_by_object_type():
    eng = L1JoinEngine()
    eng.create_join(L1JoinConfig(object_type="A", primary_dataset="da", primary_key="id"))
    eng.create_join(L1JoinConfig(object_type="B", primary_dataset="db", primary_key="id"))
    assert len(eng.list_joins()) == 2
    assert len(eng.list_joins(object_type="A")) == 1


def test_l1_join_preview():
    eng = L1JoinEngine()
    config = eng.create_join(L1JoinConfig(
        object_type="Employee",
        primary_dataset="ds_emp",
        primary_key="emp_id",
        joins=[JoinSpec(dataset="ds_dept", left_key="dept_id", right_key="dept_id", columns=["dept_name"])],
    ))
    preview = eng.preview_join(config.id)
    assert preview["objectType"] == "Employee"
    assert preview["totalColumns"] > 0
    col_names = [c["name"] for c in preview["columns"]]
    assert any("dept_name" in n for n in col_names)


def test_l1_join_preview_all_columns_when_empty():
    eng = L1JoinEngine()
    config = eng.create_join(L1JoinConfig(
        object_type="OT",
        primary_dataset="ds1",
        primary_key="id",
        joins=[JoinSpec(dataset="ds2", left_key="fk", right_key="id")],  # columns 空
    ))
    preview = eng.preview_join(config.id)
    col_names = [c["name"] for c in preview["columns"]]
    # 应该至少包含主表 key 和 join 表 key
    assert any("id" in n for n in col_names)


def test_l1_join_delete():
    eng = L1JoinEngine()
    config = eng.create_join(L1JoinConfig(object_type="X", primary_dataset="dx", primary_key="id"))
    assert eng.delete_join(config.id) is True
    with pytest.raises(L1JoinError):
        eng.get_join(config.id)


def test_computed_property_create_and_get():
    eng = L1JoinEngine()
    prop = eng.create_computed(ComputedProperty(
        object_type="Employee",
        property_name="full_name",
        function_name="concat",
        input_mapping={"first": "first_name", "last": "last_name"},
        output_type="string",
    ))
    fetched = eng.get_computed(prop.id)
    assert fetched.property_name == "full_name"
    assert fetched.function_name == "concat"


def test_computed_property_list_filter():
    eng = L1JoinEngine()
    eng.create_computed(ComputedProperty(object_type="A", property_name="p1", function_name="f"))
    eng.create_computed(ComputedProperty(object_type="B", property_name="p2", function_name="f"))
    assert len(eng.list_computed()) == 2
    assert len(eng.list_computed(object_type="A")) == 1


def test_computed_property_delete():
    eng = L1JoinEngine()
    prop = eng.create_computed(ComputedProperty(object_type="X", property_name="p", function_name="f"))
    assert eng.delete_computed(prop.id) is True
    with pytest.raises(L1JoinError):
        eng.get_computed(prop.id)
