"""221plan · 生成评测类型 — 单元测试。"""
import pytest

from aos_api.aip_eval_gen import get_engine, EvalGenItem, EvalGenEngine


@pytest.fixture(autouse=True)
def reset_engine():
    """每条测试前清空引擎，确保隔离。"""
    get_engine().reset()
    yield


def test_create_and_get():
    engine = get_engine()
    item = engine.create("test-item", {"key": "value"})
    assert item.name == "test-item"
    assert item.config == {"key": "value"}
    fetched = engine.get(item.id)
    assert fetched is not None
    assert fetched.id == item.id


def test_list():
    engine = get_engine()
    engine.create("item-1")
    engine.create("item-2")
    engine.create("item-3")
    assert len(engine.list()) == 3


def test_update():
    engine = get_engine()
    item = engine.create("original")
    updated = engine.update(item.id, name="changed", status="inactive")
    assert updated.name == "changed"
    assert updated.status == "inactive"


def test_delete():
    engine = get_engine()
    item = engine.create("to-delete")
    assert engine.delete(item.id) is True
    assert engine.get(item.id) is None
    assert engine.delete("nonexistent") is False


def test_get_nonexistent():
    engine = get_engine()
    assert engine.get("fake-id") is None


def test_update_nonexistent():
    engine = get_engine()
    with pytest.raises(KeyError):
        engine.update("fake-id", name="x")


def test_default_values():
    engine = get_engine()
    item = engine.create("defaults")
    assert item.status == "active"
    assert item.created_at > 0
    assert item.updated_at > 0


def test_config_defaults_to_empty():
    engine = get_engine()
    item = engine.create("no-config")
    assert item.config == {}


def test_singleton():
    e1 = get_engine()
    e2 = EvalGenEngine()
    assert e1 is e2
