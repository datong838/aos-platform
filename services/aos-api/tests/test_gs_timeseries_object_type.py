"""
W6 — 时间序列 Object 类型
Tests: TimeseriesObjectTypeEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.gs_timeseries_object_type import TimeseriesObjectType, TimeseriesObjectTypeEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TimeseriesObjectTypeEngine().reset()
    yield
    TimeseriesObjectTypeEngine().reset()


class TestTimeseriesObjectTypeEngine:
    def test_register(self):
        item = TimeseriesObjectType(name="test-item")
        result = TimeseriesObjectTypeEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TimeseriesObjectType(name="get-test")
        TimeseriesObjectTypeEngine().register(item)
        found = TimeseriesObjectTypeEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TimeseriesObjectTypeEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TimeseriesObjectTypeEngine().register(TimeseriesObjectType(name=f"list-{i}"))
        items = TimeseriesObjectTypeEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TimeseriesObjectType(name="original")
        TimeseriesObjectTypeEngine().register(item)
        updated = TimeseriesObjectTypeEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TimeseriesObjectTypeEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TimeseriesObjectType(name="delete-me")
        TimeseriesObjectTypeEngine().register(item)
        assert TimeseriesObjectTypeEngine().delete(item.id) is True
        assert TimeseriesObjectTypeEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TimeseriesObjectTypeEngine().register(TimeseriesObjectType(name=f"cap-{i}"))
        assert len(TimeseriesObjectTypeEngine().list()) == 100

    def test_singleton(self):
        e1 = TimeseriesObjectTypeEngine()
        e2 = TimeseriesObjectTypeEngine()
        assert e1 is e2
