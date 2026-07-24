"""
W6 — 时间序列
Tests: IdTimeseriesEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_timeseries import IdTimeseries, IdTimeseriesEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IdTimeseriesEngine().reset()
    yield
    IdTimeseriesEngine().reset()


class TestIdTimeseriesEngine:
    def test_register(self):
        item = IdTimeseries(name="test-item")
        result = IdTimeseriesEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IdTimeseries(name="get-test")
        IdTimeseriesEngine().register(item)
        found = IdTimeseriesEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IdTimeseriesEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IdTimeseriesEngine().register(IdTimeseries(name=f"list-{i}"))
        items = IdTimeseriesEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IdTimeseries(name="original")
        IdTimeseriesEngine().register(item)
        updated = IdTimeseriesEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IdTimeseriesEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IdTimeseries(name="delete-me")
        IdTimeseriesEngine().register(item)
        assert IdTimeseriesEngine().delete(item.id) is True
        assert IdTimeseriesEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IdTimeseriesEngine().register(IdTimeseries(name=f"cap-{i}"))
        assert len(IdTimeseriesEngine().list()) == 100

    def test_singleton(self):
        e1 = IdTimeseriesEngine()
        e2 = IdTimeseriesEngine()
        assert e1 is e2
