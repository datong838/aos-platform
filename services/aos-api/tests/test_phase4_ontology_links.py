"""Phase 4 · Ontology Links — 单元测试 (≥3)."""
from __future__ import annotations

import pytest

from aos_api.ontology_link_engine import get_link_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_link_engine().reset()
    yield


def test_create_and_get_link_type() -> None:
    eng = get_link_engine()
    lt = eng.create_link_type(name="customer_order", cardinality="one_to_many")
    fetched = eng.get_link_type(lt.id)
    assert fetched is not None
    assert fetched.name == "customer_order"


def test_update_link_type() -> None:
    eng = get_link_engine()
    lt = eng.create_link_type(name="lt1")
    updated = eng.update_link_type(lt.id, description="updated", cardinality="many_to_many")
    assert updated.description == "updated"
    assert updated.cardinality == "many_to_many"


def test_create_and_get_link_instance() -> None:
    eng = get_link_engine()
    lt = eng.create_link_type(name="cust_order")
    li = eng.create_link(lt.id, source_object_id="obj-1", target_object_id="obj-2")
    fetched = eng.get_link(li.id)
    assert fetched is not None
    assert fetched.source_object_id == "obj-1"


def test_list_links_filter() -> None:
    eng = get_link_engine()
    lt1 = eng.create_link_type(name="t1")
    lt2 = eng.create_link_type(name="t2")
    eng.create_link(lt1.id, "s1", "t1")
    eng.create_link(lt1.id, "s2", "t2")
    eng.create_link(lt2.id, "s3", "t3")
    items = eng.list_links(link_type_id=lt1.id)
    assert len(items) == 2


def test_update_link() -> None:
    eng = get_link_engine()
    lt = eng.create_link_type(name="lt")
    li = eng.create_link(lt.id, "s", "t")
    updated = eng.update_link(li.id, properties={"weight": 2.5})
    assert updated.properties["weight"] == 2.5


def test_delete_link_type_cascades() -> None:
    eng = get_link_engine()
    lt = eng.create_link_type(name="lt")
    eng.create_link(lt.id, "s", "t")
    assert eng.delete_link_type(lt.id) is True
    # 关联实例也被清除
    assert eng.list_links(link_type_id=lt.id) == []
