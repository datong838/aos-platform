"""
W5 — 参数描述帮助
Tests: ParamDescEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_param_desc import ParamDesc, ParamDescEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ParamDescEngine().reset()
    yield
    ParamDescEngine().reset()


class TestParamDescEngine:
    def test_register(self):
        item = ParamDesc(name="test-item")
        result = ParamDescEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ParamDesc(name="get-test")
        ParamDescEngine().register(item)
        found = ParamDescEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ParamDescEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ParamDescEngine().register(ParamDesc(name=f"list-{i}"))
        items = ParamDescEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ParamDesc(name="original")
        ParamDescEngine().register(item)
        updated = ParamDescEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ParamDescEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ParamDesc(name="delete-me")
        ParamDescEngine().register(item)
        assert ParamDescEngine().delete(item.id) is True
        assert ParamDescEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ParamDescEngine().register(ParamDesc(name=f"cap-{i}"))
        assert len(ParamDescEngine().list()) == 100

    def test_singleton(self):
        e1 = ParamDescEngine()
        e2 = ParamDescEngine()
        assert e1 is e2
