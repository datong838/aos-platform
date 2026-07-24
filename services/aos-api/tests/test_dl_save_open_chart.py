"""
W5 — 保存打开图表
Tests: SavedChartEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dl_save_open_chart import SavedChart, SavedChartEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SavedChartEngine().reset()
    yield
    SavedChartEngine().reset()


class TestSavedChartEngine:
    def test_register(self):
        item = SavedChart(name="test-item")
        result = SavedChartEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SavedChart(name="get-test")
        SavedChartEngine().register(item)
        found = SavedChartEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SavedChartEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SavedChartEngine().register(SavedChart(name=f"list-{i}"))
        items = SavedChartEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SavedChart(name="original")
        SavedChartEngine().register(item)
        updated = SavedChartEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SavedChartEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SavedChart(name="delete-me")
        SavedChartEngine().register(item)
        assert SavedChartEngine().delete(item.id) is True
        assert SavedChartEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SavedChartEngine().register(SavedChart(name=f"cap-{i}"))
        assert len(SavedChartEngine().list()) == 100

    def test_singleton(self):
        e1 = SavedChartEngine()
        e2 = SavedChartEngine()
        assert e1 is e2
