"""
W5 — 值来源选择
Tests: ValueSourceEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_value_source import ValueSource, ValueSourceEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ValueSourceEngine().reset()
    yield
    ValueSourceEngine().reset()


class TestValueSourceEngine:
    def test_register(self):
        item = ValueSource(name="test-item")
        result = ValueSourceEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ValueSource(name="get-test")
        ValueSourceEngine().register(item)
        found = ValueSourceEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ValueSourceEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ValueSourceEngine().register(ValueSource(name=f"list-{i}"))
        items = ValueSourceEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ValueSource(name="original")
        ValueSourceEngine().register(item)
        updated = ValueSourceEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ValueSourceEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ValueSource(name="delete-me")
        ValueSourceEngine().register(item)
        assert ValueSourceEngine().delete(item.id) is True
        assert ValueSourceEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ValueSourceEngine().register(ValueSource(name=f"cap-{i}"))
        assert len(ValueSourceEngine().list()) == 100

    def test_singleton(self):
        e1 = ValueSourceEngine()
        e2 = ValueSourceEngine()
        assert e1 is e2
