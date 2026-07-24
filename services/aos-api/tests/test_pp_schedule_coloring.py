"""
W5 — 调度配置着色
Tests: ScheduleColoringEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_schedule_coloring import ScheduleColoring, ScheduleColoringEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ScheduleColoringEngine().reset()
    yield
    ScheduleColoringEngine().reset()


class TestScheduleColoringEngine:
    def test_register(self):
        item = ScheduleColoring(name="test-item")
        result = ScheduleColoringEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ScheduleColoring(name="get-test")
        ScheduleColoringEngine().register(item)
        found = ScheduleColoringEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ScheduleColoringEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ScheduleColoringEngine().register(ScheduleColoring(name=f"list-{i}"))
        items = ScheduleColoringEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ScheduleColoring(name="original")
        ScheduleColoringEngine().register(item)
        updated = ScheduleColoringEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ScheduleColoringEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ScheduleColoring(name="delete-me")
        ScheduleColoringEngine().register(item)
        assert ScheduleColoringEngine().delete(item.id) is True
        assert ScheduleColoringEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ScheduleColoringEngine().register(ScheduleColoring(name=f"cap-{i}"))
        assert len(ScheduleColoringEngine().list()) == 100

    def test_singleton(self):
        e1 = ScheduleColoringEngine()
        e2 = ScheduleColoringEngine()
        assert e1 is e2
