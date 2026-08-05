"""221plan · Model Catalog 登记 — 单元测试。"""
import pytest

from aos_api.aip_model_catalog import ModelCatalogEngine, get_engine
from aos_api.tenant_scope import TenantScope


TEST_SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture(autouse=True)
def reset_engine():
    """每条测试前清空引擎，确保隔离。"""
    get_engine().reset_all_for_tests()
    yield


def test_create_and_get():
    engine = get_engine()
    item = engine.create(TEST_SCOPE, "test-item", {"key": "value"})
    assert item.name == "test-item"
    assert item.config == {"key": "value"}
    fetched = engine.get(TEST_SCOPE, item.id)
    assert fetched is not None
    assert fetched.id == item.id


def test_list():
    engine = get_engine()
    engine.create(TEST_SCOPE, "item-1")
    engine.create(TEST_SCOPE, "item-2")
    engine.create(TEST_SCOPE, "item-3")
    assert len(engine.list(TEST_SCOPE)) == 3


def test_update():
    engine = get_engine()
    item = engine.create(TEST_SCOPE, "original")
    updated = engine.update(TEST_SCOPE, item.id, name="changed", status="inactive")
    assert updated.name == "changed"
    assert updated.status == "inactive"


def test_delete():
    engine = get_engine()
    item = engine.create(TEST_SCOPE, "to-delete")
    assert engine.delete(TEST_SCOPE, item.id) is True
    assert engine.get(TEST_SCOPE, item.id) is None
    assert engine.delete(TEST_SCOPE, "nonexistent") is False


def test_get_nonexistent():
    engine = get_engine()
    assert engine.get(TEST_SCOPE, "fake-id") is None


def test_update_nonexistent():
    engine = get_engine()
    with pytest.raises(KeyError):
        engine.update(TEST_SCOPE, "fake-id", name="x")


def test_default_values():
    engine = get_engine()
    item = engine.create(TEST_SCOPE, "defaults")
    assert item.status == "active"
    assert item.created_at > 0
    assert item.updated_at > 0


def test_config_defaults_to_empty():
    engine = get_engine()
    item = engine.create(TEST_SCOPE, "no-config")
    assert item.config == {}


def test_singleton():
    e1 = get_engine()
    e2 = ModelCatalogEngine()
    assert e1 is e2
