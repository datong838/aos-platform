"""
W5 — 增量性能维护
Tests: IncrementalPerfEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_incremental_perf import IncrementalPerf, IncrementalPerfEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IncrementalPerfEngine().reset()
    yield
    IncrementalPerfEngine().reset()


class TestIncrementalPerfEngine:
    def test_register(self):
        item = IncrementalPerf(name="test-item")
        result = IncrementalPerfEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IncrementalPerf(name="get-test")
        IncrementalPerfEngine().register(item)
        found = IncrementalPerfEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IncrementalPerfEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IncrementalPerfEngine().register(IncrementalPerf(name=f"list-{i}"))
        items = IncrementalPerfEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IncrementalPerf(name="original")
        IncrementalPerfEngine().register(item)
        updated = IncrementalPerfEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IncrementalPerfEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IncrementalPerf(name="delete-me")
        IncrementalPerfEngine().register(item)
        assert IncrementalPerfEngine().delete(item.id) is True
        assert IncrementalPerfEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IncrementalPerfEngine().register(IncrementalPerf(name=f"cap-{i}"))
        assert len(IncrementalPerfEngine().list()) == 100

    def test_singleton(self):
        e1 = IncrementalPerfEngine()
        e2 = IncrementalPerfEngine()
        assert e1 is e2
