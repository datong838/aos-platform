"""
W5 — 计划面板
Tests: SchedulePanelEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_schedule_panel import SchedulePanel, SchedulePanelEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SchedulePanelEngine().reset()
    yield
    SchedulePanelEngine().reset()


class TestSchedulePanelEngine:
    def test_register(self):
        item = SchedulePanel(name="test-item")
        result = SchedulePanelEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SchedulePanel(name="get-test")
        SchedulePanelEngine().register(item)
        found = SchedulePanelEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SchedulePanelEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SchedulePanelEngine().register(SchedulePanel(name=f"list-{i}"))
        items = SchedulePanelEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SchedulePanel(name="original")
        SchedulePanelEngine().register(item)
        updated = SchedulePanelEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SchedulePanelEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SchedulePanel(name="delete-me")
        SchedulePanelEngine().register(item)
        assert SchedulePanelEngine().delete(item.id) is True
        assert SchedulePanelEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SchedulePanelEngine().register(SchedulePanel(name=f"cap-{i}"))
        assert len(SchedulePanelEngine().list()) == 100

    def test_singleton(self):
        e1 = SchedulePanelEngine()
        e2 = SchedulePanelEngine()
        assert e1 is e2
