"""
W6 — 增量处理
Tests: IncrementalProcessEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_incremental_process import IncrementalProcess, IncrementalProcessEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IncrementalProcessEngine().reset()
    yield
    IncrementalProcessEngine().reset()


class TestIncrementalProcessEngine:
    def test_register(self):
        item = IncrementalProcess(name="test-item")
        result = IncrementalProcessEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IncrementalProcess(name="get-test")
        IncrementalProcessEngine().register(item)
        found = IncrementalProcessEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IncrementalProcessEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IncrementalProcessEngine().register(IncrementalProcess(name=f"list-{i}"))
        items = IncrementalProcessEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IncrementalProcess(name="original")
        IncrementalProcessEngine().register(item)
        updated = IncrementalProcessEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IncrementalProcessEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IncrementalProcess(name="delete-me")
        IncrementalProcessEngine().register(item)
        assert IncrementalProcessEngine().delete(item.id) is True
        assert IncrementalProcessEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IncrementalProcessEngine().register(IncrementalProcess(name=f"cap-{i}"))
        assert len(IncrementalProcessEngine().list()) == 100

    def test_singleton(self):
        e1 = IncrementalProcessEngine()
        e2 = IncrementalProcessEngine()
        assert e1 is e2
