"""
W5 — 高级调度选项
Tests: AdvancedScheduleEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_advanced_schedule import AdvancedSchedule, AdvancedScheduleEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AdvancedScheduleEngine().reset()
    yield
    AdvancedScheduleEngine().reset()


class TestAdvancedScheduleEngine:
    def test_register(self):
        item = AdvancedSchedule(name="test-item")
        result = AdvancedScheduleEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AdvancedSchedule(name="get-test")
        AdvancedScheduleEngine().register(item)
        found = AdvancedScheduleEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AdvancedScheduleEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AdvancedScheduleEngine().register(AdvancedSchedule(name=f"list-{i}"))
        items = AdvancedScheduleEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AdvancedSchedule(name="original")
        AdvancedScheduleEngine().register(item)
        updated = AdvancedScheduleEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AdvancedScheduleEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AdvancedSchedule(name="delete-me")
        AdvancedScheduleEngine().register(item)
        assert AdvancedScheduleEngine().delete(item.id) is True
        assert AdvancedScheduleEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AdvancedScheduleEngine().register(AdvancedSchedule(name=f"cap-{i}"))
        assert len(AdvancedScheduleEngine().list()) == 100

    def test_singleton(self):
        e1 = AdvancedScheduleEngine()
        e2 = AdvancedScheduleEngine()
        assert e1 is e2
