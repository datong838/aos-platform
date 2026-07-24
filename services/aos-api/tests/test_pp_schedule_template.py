"""
W5 — 常见调度模板
Tests: ScheduleTemplateEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_schedule_template import ScheduleTemplate, ScheduleTemplateEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ScheduleTemplateEngine().reset()
    yield
    ScheduleTemplateEngine().reset()


class TestScheduleTemplateEngine:
    def test_register(self):
        item = ScheduleTemplate(name="test-item")
        result = ScheduleTemplateEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ScheduleTemplate(name="get-test")
        ScheduleTemplateEngine().register(item)
        found = ScheduleTemplateEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ScheduleTemplateEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ScheduleTemplateEngine().register(ScheduleTemplate(name=f"list-{i}"))
        items = ScheduleTemplateEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ScheduleTemplate(name="original")
        ScheduleTemplateEngine().register(item)
        updated = ScheduleTemplateEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ScheduleTemplateEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ScheduleTemplate(name="delete-me")
        ScheduleTemplateEngine().register(item)
        assert ScheduleTemplateEngine().delete(item.id) is True
        assert ScheduleTemplateEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ScheduleTemplateEngine().register(ScheduleTemplate(name=f"cap-{i}"))
        assert len(ScheduleTemplateEngine().list()) == 100

    def test_singleton(self):
        e1 = ScheduleTemplateEngine()
        e2 = ScheduleTemplateEngine()
        assert e1 is e2
