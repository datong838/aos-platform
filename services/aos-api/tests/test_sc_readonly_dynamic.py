"""
W5 — 只读动态双模式
Tests: ReadonlyDynamicEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.sc_readonly_dynamic import ReadonlyDynamic, ReadonlyDynamicEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ReadonlyDynamicEngine().reset()
    yield
    ReadonlyDynamicEngine().reset()


class TestReadonlyDynamicEngine:
    def test_register(self):
        item = ReadonlyDynamic(name="test-item")
        result = ReadonlyDynamicEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ReadonlyDynamic(name="get-test")
        ReadonlyDynamicEngine().register(item)
        found = ReadonlyDynamicEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ReadonlyDynamicEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ReadonlyDynamicEngine().register(ReadonlyDynamic(name=f"list-{i}"))
        items = ReadonlyDynamicEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ReadonlyDynamic(name="original")
        ReadonlyDynamicEngine().register(item)
        updated = ReadonlyDynamicEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ReadonlyDynamicEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ReadonlyDynamic(name="delete-me")
        ReadonlyDynamicEngine().register(item)
        assert ReadonlyDynamicEngine().delete(item.id) is True
        assert ReadonlyDynamicEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ReadonlyDynamicEngine().register(ReadonlyDynamic(name=f"cap-{i}"))
        assert len(ReadonlyDynamicEngine().list()) == 100

    def test_singleton(self):
        e1 = ReadonlyDynamicEngine()
        e2 = ReadonlyDynamicEngine()
        assert e1 is e2
