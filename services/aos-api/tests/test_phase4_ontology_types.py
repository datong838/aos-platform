"""Phase 4 · Ontology Types — 单元测试 (≥10)."""
from __future__ import annotations

import pytest

from aos_api.ontology_engine import get_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_list_object_types_empty() -> None:
    eng = get_engine()
    items, total = eng.list_object_types()
    assert total == 0
    assert items == []


def test_create_and_get_object_type() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer", display_name="Customer")
    fetched = eng.get_object_type(ot.id)
    assert fetched is not None
    assert fetched.name == "customer"


def test_update_object_type() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="order")
    updated = eng.update_object_type(ot.id, display_name="Order Updated", status="active")
    assert updated.display_name == "Order Updated"
    assert updated.status == "active"


def test_get_object_type_not_found() -> None:
    eng = get_engine()
    assert eng.get_object_type("nope") is None


def test_count_instances() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="product")
    eng.create_object(ot.id, name="P1")
    eng.create_object(ot.id, name="P2")
    assert eng.count_instances(ot.id) == 2


def test_list_objects_filter() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer")
    eng.create_object(ot.id, name="Alice")
    eng.create_object(ot.id, name="Bob")
    items, total = eng.list_objects(object_type_id=ot.id)
    assert total == 2
    assert len(items) == 2


def test_list_objects_search() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer")
    eng.create_object(ot.id, name="Alice")
    eng.create_object(ot.id, name="Bob")
    items, total = eng.list_objects(search="ali")
    assert total == 1
    assert items[0].name == "Alice"


def test_get_object() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="supplier")
    obj = eng.create_object(ot.id, name="S1", properties={"country": "USA"})
    fetched = eng.get_object(obj.id)
    assert fetched is not None
    assert fetched.properties["country"] == "USA"


def test_add_and_list_properties() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="invoice")
    prop = eng.add_property(ot.id, name="amount", datatype="double")
    props = eng.list_properties(ot.id)
    assert len(props) == 1
    assert props[0].id == prop.id


def test_update_property_keeps_name_stable_and_delete_cleans_mapping() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="invoice")
    prop = eng.add_property(ot.id, name="amount", datatype="double")
    eng.set_column_mapping(ot.id, [{"source_column": "amount_col", "target_property": "amount"}])
    updated = eng.update_property(ot.id, prop.id, name="renamed", description="Money")
    assert updated.name == "amount"
    assert updated.description == "Money"
    assert eng.delete_property(ot.id, prop.id) is True
    assert eng.list_properties(ot.id) == []
    assert eng.list_column_mapping(ot.id) == []


def test_automap() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="shipment")
    eng.add_property(ot.id, name="tracking_no")
    mappings = eng.automap(ot.id, ["tracking_no", "unknown_col"])
    assert len(mappings) == 2
    mapped = [m for m in mappings if m.target_property == "tracking_no"]
    assert len(mapped) == 1
    skipped = [m for m in mappings if m.status == "skipped"]
    assert len(skipped) == 1


def test_column_mapping_set_and_get() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer")
    eng.set_column_mapping(
        ot.id,
        [{"source_column": "name", "target_property": "name", "confidence": 0.9}],
    )
    items = eng.list_column_mapping(ot.id)
    assert len(items) == 1
    assert items[0].target_property == "name"


def test_preview() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="product")
    eng.add_property(ot.id, name="sku")
    eng.create_object(ot.id, name="P1", properties={"sku": "X1"})
    result = eng.preview(ot.id)
    assert result["columns"] == ["sku"]
    assert result["rows"][0]["sku"] == "X1"
    assert result["total"] == 1


def test_recent() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer")
    eng.add_recent(ot.id, user_id="u1")
    eng.add_recent(ot.id, user_id="u1")
    items = eng.list_recent(user_id="u1")
    assert len(items) == 2


def test_recent_user_isolation() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer")
    eng.add_recent(ot.id, user_id="u1")
    eng.add_recent(ot.id, user_id="u2")
    assert len(eng.list_recent(user_id="u1")) == 1
    assert len(eng.list_recent(user_id="u2")) == 1


def test_delete_object_type() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="to_delete")
    assert eng.delete_object_type(ot.id) is True
    assert eng.get_object_type(ot.id) is None


def test_list_object_types_search_and_sort() -> None:
    eng = get_engine()
    eng.create_object_type(name="alpha", display_name="A")
    eng.create_object_type(name="beta", display_name="B")
    items, total = eng.list_object_types(search="alph")
    assert total == 1
    assert items[0].name == "alpha"
