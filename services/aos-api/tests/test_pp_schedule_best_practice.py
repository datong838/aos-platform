"""
W5 — 调度最佳实践
Tests: ScheduleBestPracticeEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_schedule_best_practice import ScheduleBestPractice, ScheduleBestPracticeEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ScheduleBestPracticeEngine().reset()
    yield
    ScheduleBestPracticeEngine().reset()


class TestScheduleBestPracticeEngine:
    def test_register(self):
        item = ScheduleBestPractice(name="test-item")
        result = ScheduleBestPracticeEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ScheduleBestPractice(name="get-test")
        ScheduleBestPracticeEngine().register(item)
        found = ScheduleBestPracticeEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ScheduleBestPracticeEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ScheduleBestPracticeEngine().register(ScheduleBestPractice(name=f"list-{i}"))
        items = ScheduleBestPracticeEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ScheduleBestPractice(name="original")
        ScheduleBestPracticeEngine().register(item)
        updated = ScheduleBestPracticeEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ScheduleBestPracticeEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ScheduleBestPractice(name="delete-me")
        ScheduleBestPracticeEngine().register(item)
        assert ScheduleBestPracticeEngine().delete(item.id) is True
        assert ScheduleBestPracticeEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ScheduleBestPracticeEngine().register(ScheduleBestPractice(name=f"cap-{i}"))
        assert len(ScheduleBestPracticeEngine().list()) == 100

    def test_singleton(self):
        e1 = ScheduleBestPracticeEngine()
        e2 = ScheduleBestPracticeEngine()
        assert e1 is e2
