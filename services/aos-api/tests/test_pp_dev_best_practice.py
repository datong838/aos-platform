"""
W5 — 开发最佳实践
Tests: DevBestPracticeEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_dev_best_practice import DevBestPractice, DevBestPracticeEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DevBestPracticeEngine().reset()
    yield
    DevBestPracticeEngine().reset()


class TestDevBestPracticeEngine:
    def test_register(self):
        item = DevBestPractice(name="test-item")
        result = DevBestPracticeEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DevBestPractice(name="get-test")
        DevBestPracticeEngine().register(item)
        found = DevBestPracticeEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DevBestPracticeEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DevBestPracticeEngine().register(DevBestPractice(name=f"list-{i}"))
        items = DevBestPracticeEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DevBestPractice(name="original")
        DevBestPracticeEngine().register(item)
        updated = DevBestPracticeEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DevBestPracticeEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DevBestPractice(name="delete-me")
        DevBestPracticeEngine().register(item)
        assert DevBestPracticeEngine().delete(item.id) is True
        assert DevBestPracticeEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DevBestPracticeEngine().register(DevBestPractice(name=f"cap-{i}"))
        assert len(DevBestPracticeEngine().list()) == 100

    def test_singleton(self):
        e1 = DevBestPracticeEngine()
        e2 = DevBestPracticeEngine()
        assert e1 is e2
