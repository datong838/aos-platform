"""
W5 — 日程安排日历
Tests: CalendarViewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.sc_calendar_view import CalendarView, CalendarViewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CalendarViewEngine().reset()
    yield
    CalendarViewEngine().reset()


class TestCalendarViewEngine:
    def test_register(self):
        item = CalendarView(name="test-item")
        result = CalendarViewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CalendarView(name="get-test")
        CalendarViewEngine().register(item)
        found = CalendarViewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CalendarViewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CalendarViewEngine().register(CalendarView(name=f"list-{i}"))
        items = CalendarViewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CalendarView(name="original")
        CalendarViewEngine().register(item)
        updated = CalendarViewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CalendarViewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CalendarView(name="delete-me")
        CalendarViewEngine().register(item)
        assert CalendarViewEngine().delete(item.id) is True
        assert CalendarViewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CalendarViewEngine().register(CalendarView(name=f"cap-{i}"))
        assert len(CalendarViewEngine().list()) == 100

    def test_singleton(self):
        e1 = CalendarViewEngine()
        e2 = CalendarViewEngine()
        assert e1 is e2
