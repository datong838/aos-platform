"""
W5 — 输入输出分类
Tests: IOClassifyEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_io_classify import IOClassify, IOClassifyEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IOClassifyEngine().reset()
    yield
    IOClassifyEngine().reset()


class TestIOClassifyEngine:
    def test_register(self):
        item = IOClassify(name="test-item")
        result = IOClassifyEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IOClassify(name="get-test")
        IOClassifyEngine().register(item)
        found = IOClassifyEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IOClassifyEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IOClassifyEngine().register(IOClassify(name=f"list-{i}"))
        items = IOClassifyEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IOClassify(name="original")
        IOClassifyEngine().register(item)
        updated = IOClassifyEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IOClassifyEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IOClassify(name="delete-me")
        IOClassifyEngine().register(item)
        assert IOClassifyEngine().delete(item.id) is True
        assert IOClassifyEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IOClassifyEngine().register(IOClassify(name=f"cap-{i}"))
        assert len(IOClassifyEngine().list()) == 100

    def test_singleton(self):
        e1 = IOClassifyEngine()
        e2 = IOClassifyEngine()
        assert e1 is e2
