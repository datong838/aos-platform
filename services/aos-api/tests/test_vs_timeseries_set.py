"""
W6 — Time series set
Tests: TimeseriesSetEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.vs_timeseries_set import TimeseriesSet, TimeseriesSetEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TimeseriesSetEngine().reset()
    yield
    TimeseriesSetEngine().reset()


class TestTimeseriesSetEngine:
    def test_register(self):
        item = TimeseriesSet(name="test-item")
        result = TimeseriesSetEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TimeseriesSet(name="get-test")
        TimeseriesSetEngine().register(item)
        found = TimeseriesSetEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TimeseriesSetEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TimeseriesSetEngine().register(TimeseriesSet(name=f"list-{i}"))
        items = TimeseriesSetEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TimeseriesSet(name="original")
        TimeseriesSetEngine().register(item)
        updated = TimeseriesSetEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TimeseriesSetEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TimeseriesSet(name="delete-me")
        TimeseriesSetEngine().register(item)
        assert TimeseriesSetEngine().delete(item.id) is True
        assert TimeseriesSetEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TimeseriesSetEngine().register(TimeseriesSet(name=f"cap-{i}"))
        assert len(TimeseriesSetEngine().list()) == 100

    def test_singleton(self):
        e1 = TimeseriesSetEngine()
        e2 = TimeseriesSetEngine()
        assert e1 is e2
